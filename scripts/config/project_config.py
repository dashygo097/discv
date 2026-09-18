#!/usr/bin/env python3
"""Validate Project.toml and generate build-system projections."""

import argparse
import hashlib
import json
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


GENERATOR_VERSION = "0.2.0"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RTL_SOURCE_SUFFIXES = {".sv", ".v"}
RTL_HEADER_SUFFIXES = {".svh", ".vh", ".h"}
GENERATED_HEADER_NAMES = {"cfg.svh"}


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
            "flow",
            "workflow",
        },
        "<root>",
    )
    if raw.get("schema_version") != 1:
        raise ConfigError("schema_version: expected integer 1")

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
        {"python", "required_commands", "required_variables"},
        "environment",
    )
    python = require_string(environment, "python", "environment")
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

    flow = require_table(raw, "flow")
    reject_unknown(flow, {"lint"}, "flow")
    lint = flow.get("lint")
    if not isinstance(lint, dict):
        raise ConfigError("flow.lint: expected a table")
    reject_unknown(lint, {"enabled", "tool", "options"}, "flow.lint")
    lint_enabled = require_bool(lint, "enabled", "flow.lint")
    lint_tool = lint.get("tool")
    if not isinstance(lint_tool, str):
        raise ConfigError("flow.lint.tool: expected a string")
    lint_options = string_list(lint.get("options", []), "flow.lint.options")
    if lint_enabled and not lint_tool:
        raise ConfigError("flow.lint.tool: required when lint is enabled")
    supported_lint_tools = {"spyglass", "verilator"}
    if lint_enabled and lint_tool not in supported_lint_tools:
        supported = ", ".join(sorted(supported_lint_tools))
        raise ConfigError(f"flow.lint.tool: supported values are {supported}")

    workflow = require_table(raw, "workflow")
    reject_unknown(workflow, {"stages"}, "workflow")
    stages = string_list(workflow.get("stages", []), "workflow.stages")
    unsupported = sorted(set(stages) - {"lint"})
    if unsupported:
        raise ConfigError(
            f"workflow.stages: unsupported stage(s): {', '.join(unsupported)}"
        )
    if "lint" in stages and not lint_enabled:
        raise ConfigError(
            "workflow.stages: lint is listed but flow.lint.enabled is false"
        )
    if len(stages) != len(set(stages)):
        raise ConfigError("workflow.stages: duplicate stages are not allowed")

    return {
        "schema_version": 1,
        "parameters": normalized_parameters,
        "rtl": {
            "top": top,
            **discovered_rtl,
            "defines": normalized_defines,
        },
        "build": {"jobs": jobs},
        "environment": {
            "python": python,
            "required_commands": required_commands,
            "required_variables": required_variables,
        },
        "flow": {
            "lint": {
                "enabled": lint_enabled,
                "tool": lint_tool,
                "options": lint_options,
            }
        },
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


def make_escape(value):
    return value.replace("$", "$$").replace("#", "\\#")


def make_project_path(path):
    return f"$(PROJECT_ROOT)/{make_escape(path)}"


def render_makefile(config, digest, project_root):
    project_top = make_escape(config["rtl"]["top"])
    lint_enabled = "1" if config["flow"]["lint"]["enabled"] else "0"
    lint_tool = make_escape(config["flow"]["lint"]["tool"])
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
            f"LINT_ENABLED := {lint_enabled}\n",
            f"LINT_TOOL := {lint_tool}\n",
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
    lint = config["flow"]["lint"]
    rtl_top = shlex.quote(config["rtl"]["top"])
    project_python = shlex.quote(config["environment"]["python"])
    lint_enabled = "1" if lint["enabled"] else "0"
    lint_tool = shlex.quote(lint["tool"])
    return "".join(
        [
            header("#", digest),
            f"PROJECT_CONFIG_DIGEST={shlex.quote(digest)}\n",
            f"RTL_TOP={rtl_top}\n",
            f"BUILD_JOBS={config['build']['jobs']}\n",
            f"PROJECT_PYTHON={project_python}\n",
            f"LINT_ENABLED={lint_enabled}\n",
            f"LINT_TOOL={lint_tool}\n",
            f"LINT_OPTION_COUNT={len(lint['options'])}\n",
            shell_array("LINT_OPTIONS", lint["options"]),
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


def render_outputs(config, config_path, project_root, output_dir):
    digest = config_digest(config)
    resolved = resolved_configuration(config)
    manifest = {
        **resolved,
        "configuration_digest": digest,
        "generator": {
            "name": "project_config.py",
            "version": GENERATOR_VERSION,
        },
        "project_file": relative_project_path(project_root, config_path),
        "outputs": [
            "cfg.svh",
            "manifest.json",
            "project.env",
            "project.mk",
            "rtl.f",
        ],
    }
    return {
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "project.mk": render_makefile(config, digest, project_root),
        "project.env": render_environment(config, digest),
        "cfg.svh": render_svh(config, digest),
        "rtl.f": render_filelist(config, digest, project_root, output_dir),
    }


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


def check_outputs(output_dir, outputs):
    stale = []
    for name, expected in sorted(outputs.items()):
        path = output_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(name)
    if stale:
        raise ConfigError(f"missing or stale generated file(s): {', '.join(stale)}")


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
                atomic_write(output_dir / name, content)
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
