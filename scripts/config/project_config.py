#!/usr/bin/env python3
"""Validate Project.toml and generate build-system projections."""

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.stderr.write(
            "ERROR: TOML parser unavailable; install scripts/config/requirements.txt\n"
        )
        raise SystemExit(2)


GENERATOR_VERSION = "0.5.0"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RTL_SOURCE_SUFFIXES = {".sv", ".v"}
RTL_HEADER_SUFFIXES = {".svh", ".vh", ".h"}
GENERATED_HEADER_NAMES = {"cfg.svh"}
MANAGED_OUTPUT_NAMES = {
    ".done",
    "cfg.svh",
    "constraints.sdc",
    "manifest.json",
    "project.env",
    "project.mk",
    "rtl.f",
    "rtl.tcl",
    "synth.dc.tcl",
}


class ConfigError(Exception):
    pass


def reject_unknown(table, allowed, location):
    unknown = sorted(set(table) - set(allowed))
    if unknown:
        raise ConfigError(f"{location}: unknown key(s): {', '.join(unknown)}")


def require_string(table, key, location):
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{location}.{key}: expected a non-empty string")
    return value


def string_list(value, location):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{location}: expected an array of strings")
    return value


def require_table(raw, key):
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key}: expected a table")
    return value


def require_bool(table, key, location):
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{location}.{key}: expected a boolean")
    return value


def number(value, location, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{location}: expected a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ConfigError(f"{location}: expected a finite number")
    if positive and normalized <= 0:
        raise ConfigError(f"{location}: expected a positive number")
    if not positive and normalized < 0:
        raise ConfigError(f"{location}: expected a non-negative number")
    return normalized


def optional_number(table, key, location, *, positive=False):
    if key not in table:
        return None
    return number(table[key], f"{location}.{key}", positive=positive)


def configuration_path(project_root, value, location, suffix=None):
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{location}: expected a non-empty path string")
    if "$" in value:
        raise ConfigError(f"{location}: environment-variable expansion is not supported")
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    normalized = path.resolve()
    if suffix is not None and normalized.suffix.lower() != suffix:
        raise ConfigError(f"{location}: expected a {suffix} file: {value}")
    return str(normalized)


def project_path(project_root, value, location):
    project_root = project_root.resolve()
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"{location}: expected a path relative to the project root")
    resolved = (project_root / path).resolve()
    if os.path.commonpath([str(project_root), str(resolved)]) != str(project_root):
        raise ConfigError(f"{location}: path resolves outside the project root")
    return resolved


def relative_project_path(project_root, path):
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def absolute_project_path(project_root, path):
    return str((project_root.resolve() / path).resolve())


def validate_include_resolution(include_dirs, headers):
    for header in headers:
        if Path(header).name.casefold() in GENERATED_HEADER_NAMES:
            raise ConfigError(f"RTL header conflicts with generated cfg.svh: {header}")

    candidates = {}
    for include_dir in include_dirs:
        include_path = Path(include_dir)
        for header in headers:
            header_path = Path(header)
            try:
                include_name = header_path.relative_to(include_path).as_posix()
            except ValueError:
                continue
            candidates.setdefault(include_name, set()).add(header)

    ambiguities = {
        include_name: sorted(paths)
        for include_name, paths in candidates.items()
        if len(paths) > 1
    }
    if ambiguities:
        details = []
        for include_name, paths in sorted(ambiguities.items()):
            details.append(f'  "{include_name}" resolves to:')
            details.extend(f"    {path}" for path in paths)
        raise ConfigError("ambiguous RTL include resolution:\n" + "\n".join(details))


def discover_rtl_filesets(rtl, project_root):
    filesets = rtl.get("filesets")
    if not isinstance(filesets, list) or not filesets:
        raise ConfigError("rtl.filesets: expected a non-empty array of tables")

    normalized_filesets = []
    names = set()
    source_owners = {}
    sources = []
    include_dirs = []
    include_dir_set = set()
    headers = []
    header_set = set()
    discovery_dirs = []
    discovery_dir_set = set()

    for index, fileset in enumerate(filesets):
        location = f"rtl.filesets[{index}]"
        if not isinstance(fileset, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(fileset, {"name", "roots", "patterns"}, location)
        name = require_string(fileset, "name", location)
        if not IDENTIFIER.match(name):
            raise ConfigError(f"{location}.name: expected an identifier")
        if name in names:
            raise ConfigError(f"{location}.name: duplicate fileset name: {name}")
        names.add(name)

        root_names = string_list(fileset.get("roots"), f"{location}.roots")
        patterns = string_list(fileset.get("patterns"), f"{location}.patterns")
        if not root_names:
            raise ConfigError(f"{location}.roots: expected at least one root")
        if not patterns:
            raise ConfigError(f"{location}.patterns: expected at least one pattern")

        roots = []
        for root_index, root_name in enumerate(root_names):
            root_location = f"{location}.roots[{root_index}]"
            root = project_path(project_root, root_name, root_location)
            if not root.is_dir():
                raise ConfigError(f"{root_location}: directory does not exist: {root}")
            roots.append(root)

            for directory in [root] + sorted(
                (path for path in root.rglob("*") if path.is_dir()),
                key=lambda path: path.as_posix(),
            ):
                directory_name = relative_project_path(project_root, directory)
                if directory_name not in discovery_dir_set:
                    discovery_dir_set.add(directory_name)
                    discovery_dirs.append(directory_name)

            header_paths = sorted(
                (
                    path.resolve()
                    for path in root.rglob("*")
                    if path.is_file() and path.suffix.lower() in RTL_HEADER_SUFFIXES
                ),
                key=lambda path: path.as_posix(),
            )
            candidate_include_dirs = [root] + [path.parent for path in header_paths]
            for directory in candidate_include_dirs:
                directory_name = relative_project_path(project_root, directory)
                if directory_name not in include_dir_set:
                    include_dir_set.add(directory_name)
                    include_dirs.append(directory_name)
            for header_path in header_paths:
                header_name = relative_project_path(project_root, header_path)
                if header_name not in header_set:
                    header_set.add(header_name)
                    headers.append(header_name)

        normalized_patterns = []
        for pattern_index, pattern in enumerate(patterns):
            pattern_location = f"{location}.patterns[{pattern_index}]"
            pattern_path = Path(pattern)
            if not pattern or pattern_path.is_absolute() or ".." in pattern_path.parts:
                raise ConfigError(
                    f"{pattern_location}: expected a non-empty relative glob pattern"
                )
            normalized_patterns.append(pattern)

        fileset_sources = []
        for root in roots:
            for pattern_index, pattern in enumerate(normalized_patterns):
                pattern_location = f"{location}.patterns[{pattern_index}]"
                try:
                    matches = sorted(
                        (
                            path.resolve()
                            for path in root.glob(pattern)
                            if path.is_file()
                        ),
                        key=lambda path: path.as_posix(),
                    )
                except ValueError as error:
                    raise ConfigError(f"{pattern_location}: invalid glob: {error}")
                for source in matches:
                    if source.suffix.lower() not in RTL_SOURCE_SUFFIXES:
                        raise ConfigError(
                            f"{pattern_location}: matched unsupported RTL file: {source}"
                        )
                    source_name = relative_project_path(project_root, source)
                    previous_owner = source_owners.get(source_name)
                    if previous_owner is not None:
                        raise ConfigError(
                            f"{source_name}: selected more than once; first selected "
                            f"by fileset {previous_owner}, then by fileset {name}"
                        )
                    source_owners[source_name] = name
                    sources.append(source_name)
                    fileset_sources.append(source_name)

        normalized_filesets.append(
            {
                "name": name,
                "roots": [relative_project_path(project_root, root) for root in roots],
                "patterns": normalized_patterns,
                "sources": fileset_sources,
            }
        )

    if not sources:
        raise ConfigError("rtl.filesets: no RTL sources matched")
    validate_include_resolution(include_dirs, headers)
    return {
        "filesets": normalized_filesets,
        "sources": sources,
        "include_dirs": include_dirs,
        "headers": headers,
        "discovery_dirs": discovery_dirs,
    }


def normalize_clock(clock, location, *, virtual):
    if not isinstance(clock, dict):
        raise ConfigError(f"{location}: expected a table")
    reject_unknown(
        clock,
        {
            "name",
            "period",
            "waveform",
            "setup_uncertainty",
            "hold_uncertainty",
            "transition",
        },
        location,
    )
    name = require_string(clock, "name", location)
    if not IDENTIFIER.match(name):
        raise ConfigError(f"{location}.name: expected an identifier")
    period = number(clock.get("period"), f"{location}.period", positive=True)
    waveform = clock.get("waveform", [0.0, period / 2.0])
    if not isinstance(waveform, list) or len(waveform) != 2:
        raise ConfigError(f"{location}.waveform: expected an array of two numbers")
    waveform = [
        number(value, f"{location}.waveform[{index}]")
        for index, value in enumerate(waveform)
    ]
    if not 0 <= waveform[0] < waveform[1] <= period:
        raise ConfigError(
            f"{location}.waveform: expected 0 <= rise < fall <= period"
        )
    normalized = {
        "name": name,
        "period": period,
        "waveform": waveform,
        "virtual": virtual,
    }
    for key in ("setup_uncertainty", "hold_uncertainty", "transition"):
        value = optional_number(clock, key, location)
        if value is not None:
            normalized[key] = value
    return normalized


def normalize_port_constraints(entries, location, clock_names, value_keys):
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise ConfigError(f"{location}: expected an array of tables")
    normalized = []
    for index, entry in enumerate(entries):
        entry_location = f"{location}[{index}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{entry_location}: expected a table")
        allowed = {"ports"} | set(value_keys)
        reject_unknown(entry, allowed, entry_location)
        ports = string_list(entry.get("ports"), f"{entry_location}.ports")
        if not ports or any(not port for port in ports):
            raise ConfigError(f"{entry_location}.ports: expected non-empty patterns")
        item = {"ports": ports}
        if "clock" in value_keys:
            clock = require_string(entry, "clock", entry_location)
            if clock not in clock_names:
                raise ConfigError(
                    f"{entry_location}.clock: undefined clock: {clock}"
                )
            item["clock"] = clock
        value_count = 0
        for key in value_keys:
            if key == "clock":
                continue
            value = optional_number(entry, key, entry_location)
            if value is not None:
                item[key] = value
                value_count += 1
        if value_count == 0:
            names = ", ".join(key for key in value_keys if key != "clock")
            raise ConfigError(
                f"{entry_location}: expected at least one of: {names}"
            )
        normalized.append(item)
    return normalized


def normalize_constraints(raw):
    constraints = raw.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ConfigError("constraints: expected a table")
    reject_unknown(
        constraints,
        {
            "clocks",
            "virtual_clocks",
            "input_delays",
            "output_delays",
            "input_transitions",
            "output_loads",
            "design_rules",
        },
        "constraints",
    )

    clocks = []
    names = set()
    for key, virtual in (("clocks", False), ("virtual_clocks", True)):
        entries = constraints.get(key, [])
        if not isinstance(entries, list):
            raise ConfigError(f"constraints.{key}: expected an array of tables")
        for index, entry in enumerate(entries):
            location = f"constraints.{key}[{index}]"
            clock = normalize_clock(entry, location, virtual=virtual)
            if clock["name"] in names:
                raise ConfigError(f"{location}.name: duplicate clock: {clock['name']}")
            names.add(clock["name"])
            clocks.append(clock)

    design_rules = constraints.get("design_rules", {})
    if not isinstance(design_rules, dict):
        raise ConfigError("constraints.design_rules: expected a table")
    reject_unknown(
        design_rules,
        {"max_transition", "max_fanout", "max_capacitance"},
        "constraints.design_rules",
    )
    normalized_rules = {}
    for key in sorted(design_rules):
        normalized_rules[key] = number(
            design_rules[key], f"constraints.design_rules.{key}", positive=True
        )

    return {
        "clocks": clocks,
        "input_delays": normalize_port_constraints(
            constraints.get("input_delays"),
            "constraints.input_delays",
            names,
            ("clock", "max", "min"),
        ),
        "output_delays": normalize_port_constraints(
            constraints.get("output_delays"),
            "constraints.output_delays",
            names,
            ("clock", "max", "min"),
        ),
        "input_transitions": normalize_port_constraints(
            constraints.get("input_transitions"),
            "constraints.input_transitions",
            names,
            ("rise", "fall"),
        ),
        "output_loads": normalize_port_constraints(
            constraints.get("output_loads"),
            "constraints.output_loads",
            names,
            ("capacitance",),
        ),
        "design_rules": normalized_rules,
    }


def normalize_dc_synthesis(dc, project_root):
    location = "flow.synth.dc"
    if not isinstance(dc, dict):
        raise ConfigError(f"{location}: expected a table")
    reject_unknown(
        dc,
        {
            "target_libraries",
            "link_libraries",
            "synthetic_libraries",
            "min_libraries",
            "compile",
            "options",
        },
        location,
    )

    def libraries(key, suffix):
        values = string_list(dc.get(key, []), f"{location}.{key}")
        return [
            configuration_path(
                project_root, value, f"{location}.{key}[{index}]", suffix
            )
            for index, value in enumerate(values)
        ]

    target_libraries = libraries("target_libraries", ".db")
    if not target_libraries:
        raise ConfigError(f"{location}.target_libraries: expected at least one library")
    link_libraries = libraries("link_libraries", ".db")
    synthetic_libraries = libraries("synthetic_libraries", ".sldb")

    compile_mode = dc.get("compile", "ultra")
    if compile_mode not in {"standard", "ultra"}:
        raise ConfigError(f'{location}.compile: expected "standard" or "ultra"')

    min_libraries = dc.get("min_libraries", [])
    if not isinstance(min_libraries, list):
        raise ConfigError(f"{location}.min_libraries: expected an array of tables")
    normalized_pairs = []
    known_max_libraries = set(target_libraries + link_libraries)
    for index, pair in enumerate(min_libraries):
        pair_location = f"{location}.min_libraries[{index}]"
        if not isinstance(pair, dict):
            raise ConfigError(f"{pair_location}: expected a table")
        reject_unknown(pair, {"max", "min"}, pair_location)
        maximum = configuration_path(
            project_root,
            require_string(pair, "max", pair_location),
            f"{pair_location}.max",
            ".db",
        )
        minimum = configuration_path(
            project_root,
            require_string(pair, "min", pair_location),
            f"{pair_location}.min",
            ".db",
        )
        if maximum not in known_max_libraries:
            raise ConfigError(
                f"{pair_location}.max: expected a target or link library"
            )
        normalized_pairs.append({"max": maximum, "min": minimum})

    return {
        "target_libraries": target_libraries,
        "link_libraries": link_libraries,
        "synthetic_libraries": synthetic_libraries,
        "min_libraries": normalized_pairs,
        "compile": compile_mode,
        "options": string_list(dc.get("options", []), f"{location}.options"),
    }


def load_config(config_path, project_root):
    with config_path.open("rb") as stream:
        raw = tomllib.load(stream)

    reject_unknown(
        raw,
        {
            "schema_version",
            "parameters",
            "rtl",
            "build",
            "environment",
            "constraints",
            "flow",
            "workflow",
        },
        "<root>",
    )
    if raw.get("schema_version") != 3:
        raise ConfigError("schema_version: expected integer 3")

    parameters = require_table(raw, "parameters")
    normalized_parameters = {}
    for key in sorted(parameters):
        if not IDENTIFIER.match(key):
            raise ConfigError(f"parameters.{key}: invalid SystemVerilog identifier")
        value = parameters[key]
        if not isinstance(value, (str, int, bool)):
            raise ConfigError(f"parameters.{key}: expected string, integer, or boolean")
        normalized_parameters[key] = value

    rtl = require_table(raw, "rtl")
    reject_unknown(rtl, {"top", "filesets", "defines"}, "rtl")
    top = require_string(rtl, "top", "rtl")
    if not IDENTIFIER.match(top):
        raise ConfigError("rtl.top: invalid SystemVerilog identifier")
    discovered_rtl = discover_rtl_filesets(rtl, project_root)
    defines = rtl.get("defines", {})
    if not isinstance(defines, dict):
        raise ConfigError("rtl.defines: expected a table")

    normalized_defines = {}
    for key in sorted(defines):
        if not IDENTIFIER.match(key):
            raise ConfigError(f"rtl.defines.{key}: invalid identifier")
        value = defines[key]
        if not isinstance(value, (str, int, bool)):
            raise ConfigError(
                f"rtl.defines.{key}: expected string, integer, or boolean"
            )
        normalized_defines[key] = value

    build = require_table(raw, "build")
    reject_unknown(build, {"jobs"}, "build")
    jobs = build.get("jobs")
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ConfigError("build.jobs: expected a positive integer")

    environment = require_table(raw, "environment")
    reject_unknown(
        environment,
        {"required_commands", "required_variables"},
        "environment",
    )
    required_commands = string_list(
        environment.get("required_commands", []), "environment.required_commands"
    )
    required_variables = string_list(
        environment.get("required_variables", []), "environment.required_variables"
    )
    for variable in required_variables:
        if not IDENTIFIER.match(variable):
            raise ConfigError(
                f"environment.required_variables: invalid variable name: {variable}"
            )

    flow = raw.get("flow", {})
    if not isinstance(flow, dict):
        raise ConfigError("flow: expected a table")
    reject_unknown(flow, {"lint", "synth"}, "flow")
    lint = flow.get("lint", {})
    if not isinstance(lint, dict):
        raise ConfigError("flow.lint: expected a table")
    supported_lint_tools = {"spyglass", "verilator"}
    reject_unknown(lint, supported_lint_tools, "flow.lint")
    normalized_lint = {}
    for tool in sorted(lint):
        tool_config = lint[tool]
        location = f"flow.lint.{tool}"
        if not isinstance(tool_config, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(tool_config, {"options"}, location)
        normalized_lint[tool] = {
            "options": string_list(
                tool_config.get("options", []), f"{location}.options"
            )
        }

    synth = flow.get("synth", {})
    if not isinstance(synth, dict):
        raise ConfigError("flow.synth: expected a table")
    supported_synth_tools = {"dc"}
    reject_unknown(synth, supported_synth_tools, "flow.synth")
    normalized_synth = {}
    if "dc" in synth:
        normalized_synth["dc"] = normalize_dc_synthesis(synth["dc"], project_root)

    constraints = normalize_constraints(raw)

    workflow = require_table(raw, "workflow")
    reject_unknown(workflow, {"stages"}, "workflow")
    stages = string_list(workflow.get("stages", []), "workflow.stages")
    unsupported = sorted(set(stages) - {"lint", "synth"})
    if unsupported:
        raise ConfigError(
            f"workflow.stages: unsupported stage(s): {', '.join(unsupported)}"
        )
    if "lint" in stages and not normalized_lint:
        raise ConfigError(
            "workflow.stages: lint is listed but no flow.lint.<tool> table exists"
        )
    if "synth" in stages and not normalized_synth:
        raise ConfigError(
            "workflow.stages: synth is listed but no flow.synth.<tool> table exists"
        )
    if len(stages) != len(set(stages)):
        raise ConfigError("workflow.stages: duplicate stages are not allowed")

    return {
        "schema_version": 3,
        "parameters": normalized_parameters,
        "rtl": {
            "top": top,
            **discovered_rtl,
            "defines": normalized_defines,
        },
        "build": {"jobs": jobs},
        "environment": {
            "required_commands": required_commands,
            "required_variables": required_variables,
        },
        "constraints": constraints,
        "flow": {"lint": normalized_lint, "synth": normalized_synth},
        "workflow": {"stages": stages},
    }


def resolved_configuration(config):
    rtl = {
        key: value for key, value in config["rtl"].items() if key != "discovery_dirs"
    }
    return {
        "schema_version": config["schema_version"],
        "parameters": config["parameters"],
        "rtl": rtl,
        "build": config["build"],
        "environment": config["environment"],
        "constraints": config["constraints"],
        "flow": config["flow"],
        "workflow": config["workflow"],
    }


def config_digest(config):
    encoded = json.dumps(
        resolved_configuration(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def header(comment, digest):
    return (
        f"{comment} Generated by project_config.py; do not edit.\n"
        f"{comment} Configuration digest: {digest}\n"
    )


def render_filelist(config, digest, project_root, output_dir):
    lines = [header("#", digest).rstrip()]
    lines.append(f"+incdir+{output_dir}")
    lines.extend(
        f"+incdir+{absolute_project_path(project_root, path)}"
        for path in config["rtl"]["include_dirs"]
    )
    for name, value in sorted(config["rtl"]["defines"].items()):
        if isinstance(value, bool):
            if value:
                lines.append(f"+define+{name}")
        else:
            lines.append(f"+define+{name}={value}")
    lines.extend(
        absolute_project_path(project_root, path) for path in config["rtl"]["sources"]
    )
    return "\n".join(lines) + "\n"


def systemverilog_string(value):
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def systemverilog_integer(value):
    if 0 <= value <= 0xFFFFFFFF:
        return "int unsigned", f"32'd{value}"
    if 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        return "longint unsigned", f"64'd{value}"
    if -0x80000000 <= value < 0:
        return "int", f"32'sh{value & 0xFFFFFFFF:08x}"
    if -0x8000000000000000 <= value < 0:
        return "longint", f"64'sh{value & 0xFFFFFFFFFFFFFFFF:016x}"
    raise ConfigError(f"integer parameter is outside the 64-bit range: {value}")


def render_svh(config, digest):
    lines = [header("//", digest).rstrip()]
    for name, value in sorted(config["parameters"].items()):
        if isinstance(value, bool):
            literal = "1'b1" if value else "1'b0"
            lines.append(f"localparam bit {name} = {literal};")
        elif isinstance(value, int):
            parameter_type, literal = systemverilog_integer(value)
            lines.append(f"localparam {parameter_type} {name} = {literal};")
        else:
            lines.append(f"localparam string {name} = {systemverilog_string(value)};")
    return "\n".join(lines) + "\n"


def tcl_braced(value):
    value = str(value)
    if "{" in value or "}" in value or "\n" in value or "\r" in value:
        raise ConfigError(f"value cannot be represented safely in generated Tcl: {value!r}")
    return "{" + value + "}"


def tcl_list(values):
    return "[list " + " ".join(tcl_braced(value) for value in values) + "]"


def format_number(value):
    return format(value, ".15g")


def render_rtl_tcl(config, digest, project_root, output_dir):
    defines = []
    for name, value in sorted(config["rtl"]["defines"].items()):
        if isinstance(value, bool):
            if value:
                defines.append(name)
        else:
            defines.append(f"{name}={value}")
    sources = [
        absolute_project_path(project_root, path) for path in config["rtl"]["sources"]
    ]
    include_dirs = [str(output_dir)] + [
        absolute_project_path(project_root, path)
        for path in config["rtl"]["include_dirs"]
    ]
    return "".join(
        [
            header("#", digest),
            f"set RTL_TOP {tcl_braced(config['rtl']['top'])}\n",
            f"set RTL_SOURCES {tcl_list(sources)}\n",
            f"set RTL_INCLUDE_DIRS {tcl_list(include_dirs)}\n",
            f"set RTL_DEFINES {tcl_list(defines)}\n",
        ]
    )


def render_constraints_sdc(config, digest):
    constraints = config["constraints"]
    lines = [header("#", digest).rstrip()]
    lines.extend(
        [
            "proc project_require_ports {patterns context} {",
            "  set objects [get_ports -quiet $patterns]",
            "  if {[sizeof_collection $objects] == 0} {",
            '    error "constraint selector resolved to no ports: $context"',
            "  }",
            "  return $objects",
            "}",
        ]
    )

    for clock in constraints["clocks"]:
        name = clock["name"]
        period = format_number(clock["period"])
        waveform = " ".join(format_number(value) for value in clock["waveform"])
        if clock["virtual"]:
            lines.append(
                f"create_clock -name {tcl_braced(name)} -period {period} "
                f"-waveform {{{waveform}}}"
            )
        else:
            lines.extend(
                [
                    f"set project_clock_port [get_ports -quiet {tcl_list([name])}]",
                    "if {[sizeof_collection $project_clock_port] != 1} {",
                    f"  error {tcl_braced('physical clock must resolve to exactly one port: ' + name)}",
                    "}",
                    f"create_clock -name {tcl_braced(name)} -period {period} "
                    f"-waveform {{{waveform}}} $project_clock_port",
                    "unset project_clock_port",
                ]
            )
        clock_collection = f"[get_clocks {tcl_list([name])}]"
        if "setup_uncertainty" in clock:
            lines.append(
                "set_clock_uncertainty -setup "
                f"{format_number(clock['setup_uncertainty'])} {clock_collection}"
            )
        if "hold_uncertainty" in clock:
            lines.append(
                "set_clock_uncertainty -hold "
                f"{format_number(clock['hold_uncertainty'])} {clock_collection}"
            )
        if "transition" in clock:
            lines.append(
                f"set_clock_transition {format_number(clock['transition'])} "
                f"{clock_collection}"
            )

    for kind in ("input", "output"):
        for entry in constraints[f"{kind}_delays"]:
            ports = tcl_list(entry["ports"])
            context = f"{kind}_delays: {', '.join(entry['ports'])}"
            lines.append(
                f"set project_ports [project_require_ports {ports} {tcl_braced(context)}]"
            )
            for bound in ("max", "min"):
                if bound in entry:
                    lines.append(
                        f"set_{kind}_delay -{bound} {format_number(entry[bound])} "
                        f"-clock [get_clocks {tcl_list([entry['clock']])}] $project_ports"
                    )
            lines.append("unset project_ports")

    for entry in constraints["input_transitions"]:
        ports = tcl_list(entry["ports"])
        context = f"input_transitions: {', '.join(entry['ports'])}"
        lines.append(
            f"set project_ports [project_require_ports {ports} {tcl_braced(context)}]"
        )
        for edge in ("rise", "fall"):
            if edge in entry:
                lines.append(
                    f"set_input_transition -{edge} {format_number(entry[edge])} $project_ports"
                )
        lines.append("unset project_ports")

    for entry in constraints["output_loads"]:
        ports = tcl_list(entry["ports"])
        context = f"output_loads: {', '.join(entry['ports'])}"
        lines.extend(
            [
                f"set project_ports [project_require_ports {ports} {tcl_braced(context)}]",
                f"set_load {format_number(entry['capacitance'])} $project_ports",
                "unset project_ports",
            ]
        )

    rule_commands = {
        "max_transition": "set_max_transition",
        "max_fanout": "set_max_fanout",
        "max_capacitance": "set_max_capacitance",
    }
    for name, command in rule_commands.items():
        if name in constraints["design_rules"]:
            lines.append(
                f"{command} {format_number(constraints['design_rules'][name])} "
                "[current_design]"
            )
    lines.append("rename project_require_ports {}")
    return "\n".join(lines) + "\n"


def render_dc_tcl(config, digest):
    dc = config["flow"]["synth"].get("dc")
    if dc is None:
        dc = {
            "target_libraries": [],
            "link_libraries": [],
            "synthetic_libraries": [],
            "min_libraries": [],
            "compile": "ultra",
        }
    pairs = [
        f"[list {tcl_braced(pair['max'])} {tcl_braced(pair['min'])}]"
        for pair in dc["min_libraries"]
    ]
    return "".join(
        [
            header("#", digest),
            f"set SYNTH_TARGET_LIBRARIES {tcl_list(dc['target_libraries'])}\n",
            f"set SYNTH_LINK_LIBRARIES {tcl_list(dc['link_libraries'])}\n",
            f"set SYNTH_SYNTHETIC_LIBRARIES {tcl_list(dc['synthetic_libraries'])}\n",
            "set SYNTH_MIN_LIBRARY_PAIRS [list " + " ".join(pairs) + "]\n",
            f"set SYNTH_COMPILE {tcl_braced(dc['compile'])}\n",
        ]
    )


def make_escape(value):
    return value.replace("$", "$$").replace("#", "\\#")


def make_project_path(path):
    return f"$(PROJECT_ROOT)/{make_escape(path)}"


def render_makefile(config, digest, project_root):
    project_top = make_escape(config["rtl"]["top"])
    lint_tools = " ".join(make_escape(tool) for tool in config["flow"]["lint"])
    synth_tools = " ".join(make_escape(tool) for tool in config["flow"]["synth"])
    workflow_stages = " ".join(config["workflow"]["stages"])
    rtl_sources = " ".join(make_project_path(path) for path in config["rtl"]["sources"])
    rtl_headers = " ".join(make_project_path(path) for path in config["rtl"]["headers"])
    rtl_discovery_dirs = " ".join(
        make_project_path(path) for path in config["rtl"]["discovery_dirs"]
    )
    return "".join(
        [
            header("#", digest),
            f"GENERATED_PROJECT_ROOT := {make_escape(str(project_root))}\n",
            f"PROJECT_TOP := {project_top}\n",
            f"BUILD_JOBS := {config['build']['jobs']}\n",
            f"LINT_TOOLS := {lint_tools}\n",
            f"SYNTH_TOOLS := {synth_tools}\n",
            f"WORKFLOW_STAGES := {workflow_stages}\n",
            f"RTL_SOURCES := {rtl_sources}\n",
            f"RTL_HEADERS := {rtl_headers}\n",
            f"RTL_DISCOVERY_DIRS := {rtl_discovery_dirs}\n",
            f"PROJECT_CONFIG_DIGEST := {digest}\n",
        ]
    )


def shell_array(name, values):
    joined_values = " ".join(shlex.quote(str(value)) for value in values)
    return f"{name}=({joined_values})\n"


def render_environment(config, digest):
    rtl_top = shlex.quote(config["rtl"]["top"])
    lint = config["flow"]["lint"]
    synth = config["flow"]["synth"]
    lines = [
        header("#", digest),
        f"PROJECT_CONFIG_DIGEST={shlex.quote(digest)}\n",
        f"RTL_TOP={rtl_top}\n",
        f"BUILD_JOBS={config['build']['jobs']}\n",
        f"LINT_TOOL_COUNT={len(lint)}\n",
        shell_array("LINT_TOOLS", lint),
    ]
    for tool, tool_config in lint.items():
        variable_prefix = f"LINT_{tool.upper()}"
        lines.extend(
            [
                f"{variable_prefix}_OPTION_COUNT={len(tool_config['options'])}\n",
                shell_array(f"{variable_prefix}_OPTIONS", tool_config["options"]),
            ]
        )
    lines.extend(
        [
            f"SYNTH_TOOL_COUNT={len(synth)}\n",
            shell_array("SYNTH_TOOLS", synth),
        ]
    )
    if "dc" in synth:
        dc = synth["dc"]
        lines.extend(
            [
                f"SYNTH_DC_OPTION_COUNT={len(dc['options'])}\n",
                shell_array("SYNTH_DC_OPTIONS", dc["options"]),
            ]
        )
    lines.extend(
        [
            shell_array(
                "PROJECT_REQUIRED_COMMANDS", config["environment"]["required_commands"]
            ),
            shell_array(
                "PROJECT_REQUIRED_VARIABLES",
                config["environment"]["required_variables"],
            ),
            f"WORKFLOW_STAGE_COUNT={len(config['workflow']['stages'])}\n",
            shell_array("WORKFLOW_STAGES", config["workflow"]["stages"]),
        ]
    )
    return "".join(lines)


def render_outputs(config, config_path, project_root, output_dir):
    digest = config_digest(config)
    resolved = resolved_configuration(config)
    outputs = {
        "project.mk": render_makefile(config, digest, project_root),
        "project.env": render_environment(config, digest),
        "cfg.svh": render_svh(config, digest),
    }
    if config["flow"]["lint"]:
        outputs["rtl.f"] = render_filelist(
            config, digest, project_root, output_dir
        )
    if "dc" in config["flow"]["synth"]:
        outputs.update(
            {
                "constraints.sdc": render_constraints_sdc(config, digest),
                "rtl.tcl": render_rtl_tcl(
                    config, digest, project_root, output_dir
                ),
                "synth.dc.tcl": render_dc_tcl(config, digest),
            }
        )

    output_names = sorted([*outputs, "manifest.json"])
    manifest = {
        **resolved,
        "configuration_digest": digest,
        "generator": {
            "name": "project_config.py",
            "version": GENERATOR_VERSION,
        },
        "project_file": relative_project_path(project_root, config_path),
        "outputs": output_names,
    }
    outputs["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return outputs


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="." + path.name, dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        os.replace(temporary_name, str(path))
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def remove_stale_outputs(output_dir, outputs):
    stale_names = MANAGED_OUTPUT_NAMES - set(outputs)
    for name in sorted(stale_names):
        path = output_dir / name
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.exists():
            raise ConfigError(f"stale generated output is not a file: {path}")


def check_outputs(output_dir, outputs):
    stale = []
    for name, expected in sorted(outputs.items()):
        path = output_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(name)
    if stale:
        raise ConfigError(f"missing or stale generated file(s): {', '.join(stale)}")
    unexpected = sorted(
        name
        for name in MANAGED_OUTPUT_NAMES - set(outputs)
        if (output_dir / name).exists()
    )
    if unexpected:
        raise ConfigError(f"unexpected generated file(s): {', '.join(unexpected)}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "generate", "check"))
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = args.config.resolve()
    project_root = args.project_root.resolve()
    try:
        config = load_config(config_path, project_root)
        if args.command == "validate":
            print(f"Configuration is valid: {config_path}")
            return 0
        if args.output is None:
            raise ConfigError(f"--output is required for {args.command}")
        output_dir = args.output.resolve()
        outputs = render_outputs(config, config_path, project_root, output_dir)
        if args.command == "generate":
            for name, content in sorted(outputs.items()):
                if name == "manifest.json":
                    continue
                atomic_write(output_dir / name, content)
            remove_stale_outputs(output_dir, outputs)
            atomic_write(output_dir / "manifest.json", outputs["manifest.json"])
            print(f"Generated configuration: {output_dir}")
        else:
            check_outputs(output_dir, outputs)
            print(f"Generated configuration is current: {output_dir}")
        return 0
    except (ConfigError, OSError, tomllib.TOMLDecodeError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
