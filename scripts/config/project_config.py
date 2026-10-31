"""Golden project configuration and project-specific generated artifacts.

HDL collection, target filtering and dependency resolution belong to Bender.
"""

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

GENERATOR_VERSION = "1.0.0"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RISCV_MARCH = re.compile(
    r"^rv(?P<xlen>32|64)(?P<compact>[a-z0-9]+)"
    r"(?P<suffix>(?:_[a-z][a-z0-9]*)*)$"
)
RISCV_SINGLE_EXTENSION = re.compile(r"(?P<name>[a-z])(?P<version>\d+(?:p\d+)?)?")
RISCV_MULTI_EXTENSION = re.compile(r"^(?P<name>[a-z][a-z0-9]*?)(?:\d+(?:p\d+)?)?$")
ARCH_FEATURES = (
    "i",
    "e",
    "m",
    "a",
    "f",
    "d",
    "c",
    "b",
    "v",
    "zicsr",
    "zifencei",
)


class ConfigError(Exception):
    pass


def parse_riscv_march(march):
    match = RISCV_MARCH.fullmatch(march)
    if match is None:
        raise ConfigError(
            "architecture.march: expected a lowercase GCC-style RISC-V ISA "
            'string such as "rv32i" or "rv64gc"'
        )

    compact = match.group("compact")
    single_extensions = []
    offset = 0
    while offset < len(compact):
        extension_match = RISCV_SINGLE_EXTENSION.match(compact, offset)
        if extension_match is None:
            raise ConfigError(
                f"architecture.march: malformed extension near {compact[offset:]!r}"
            )
        single_extensions.append(extension_match.group("name"))
        offset = extension_match.end()

    duplicate_single_extensions = sorted(
        extension
        for extension in set(single_extensions)
        if single_extensions.count(extension) > 1
    )
    if duplicate_single_extensions:
        raise ConfigError(
            "architecture.march: duplicate single-letter extension(s): "
            + ", ".join(duplicate_single_extensions)
        )

    base = single_extensions[0]
    if base not in {"i", "e", "g"}:
        raise ConfigError('architecture.march: base ISA must be "i", "e", or "g"')
    if "g" in single_extensions[1:]:
        raise ConfigError('architecture.march: "g" is only valid as the base ISA')

    extensions = set(single_extensions)
    if base == "g":
        extensions.remove("g")
        extensions.update({"i", "m", "a", "f", "d", "zicsr", "zifencei"})

    suffix = match.group("suffix")
    for token in suffix.split("_"):
        if not token:
            continue
        extension_match = RISCV_MULTI_EXTENSION.fullmatch(token)
        if extension_match is None:
            raise ConfigError(
                f"architecture.march: malformed multi-letter extension: {token}"
            )
        extension = extension_match.group("name")
        if extension in extensions:
            raise ConfigError(f"architecture.march: duplicate extension: {extension}")
        extensions.add(extension)

    xlen = int(match.group("xlen"))
    if xlen != 32 and "e" in extensions:
        raise ConfigError("architecture.march: the E base ISA requires RV32")
    if "i" in extensions and "e" in extensions:
        raise ConfigError('architecture.march: base ISAs "i" and "e" conflict')
    return xlen, frozenset(extensions)


def reject_unknown(table, allowed, location):
    if not isinstance(table, dict):
        raise ConfigError(f"{location}: expected a table")
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


def unsigned_integer(value, location, *, positive=False, maximum=0xFFFFFFFF):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{location}: expected an integer")
    minimum = 1 if positive else 0
    if value < minimum or value > maximum:
        qualifier = "positive " if positive else ""
        raise ConfigError(
            f"{location}: expected a {qualifier}integer no greater than {maximum}"
        )
    return value


def configuration_path(project_root, value, location, suffix=None):
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{location}: expected a non-empty path string")
    if "$" in value:
        raise ConfigError(
            f"{location}: environment-variable expansion is not supported"
        )
    path = Path(value)
    if path.is_absolute():
        normalized = Path(os.path.normpath(value))
    else:
        normalized = (project_root / path).resolve()
    if suffix is not None and normalized.suffix.lower() != suffix:
        raise ConfigError(f"{location}: expected a {suffix} file: {value}")
    return str(normalized)


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
        raise ConfigError(f"{location}.waveform: expected 0 <= rise < fall <= period")
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
                raise ConfigError(f"{entry_location}.clock: undefined clock: {clock}")
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
            raise ConfigError(f"{entry_location}: expected at least one of: {names}")
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


def load_config(config_path, project_root):
    with config_path.open("rb") as stream:
        raw = tomllib.load(stream)
    reject_unknown(
        raw,
        {
            "schema_version",
            "architecture",
            "bender",
            "build",
            "environment",
            "constraints",
            "technology",
            "flow",
            "workflow",
        },
        "<root>",
    )
    if raw.get("schema_version") != 6:
        raise ConfigError("schema_version: expected 6; use the native [bender] schema")
    architecture = require_table(raw, "architecture")
    reject_unknown(architecture, {"march", "top", "reset_vector"}, "architecture")
    march = require_string(architecture, "march", "architecture")
    xlen, extensions = parse_riscv_march(march)
    top = require_string(architecture, "top", "architecture")
    if not IDENTIFIER.fullmatch(top):
        raise ConfigError("architecture.top: invalid identifier")
    architecture = dict(
        architecture,
        xlen=xlen,
        extensions=sorted(extensions),
        features={
            feature: feature in extensions
            for feature in sorted(set(ARCH_FEATURES) | extensions)
        },
        reset_vector=unsigned_integer(
            architecture.get("reset_vector"),
            "architecture.reset_vector",
            maximum=(1 << xlen) - 1,
        ),
    )
    bender = require_table(raw, "bender")
    reject_unknown(
        bender,
        {"name", "version", "sources", "dependencies", "export_include_dirs"},
        "bender",
    )
    require_string(bender, "name", "bender")
    require_string(bender, "version", "bender")
    if not isinstance(bender.get("sources"), list) or not bender["sources"]:
        raise ConfigError(
            "bender.sources: expected non-empty native Bender source groups"
        )
    if not isinstance(bender.get("dependencies", {}), dict):
        raise ConfigError("bender.dependencies: expected a table")
    build = require_table(raw, "build")
    reject_unknown(build, {"jobs", "technology", "reproducible"}, "build")
    build = {
        "jobs": unsigned_integer(build.get("jobs"), "build.jobs", positive=True),
        "technology": require_string(build, "technology", "build"),
        "reproducible": require_bool(build, "reproducible", "build")
        if "reproducible" in build
        else False,
    }
    environment = raw.get("environment", {})
    reject_unknown(
        environment,
        {"required_commands", "required_variables", "tool_versions", "packages"},
        "environment",
    )
    environment = {
        **{
            key: string_list(environment.get(key, []), "environment." + key)
            for key in ("required_commands", "required_variables")
        },
        "tool_versions": environment.get("tool_versions", {}),
        "packages": environment.get("packages", {}),
    }
    for key in ("tool_versions", "packages"):
        if not isinstance(environment[key], dict) or any(
            not isinstance(value, str) or not value
            for value in environment[key].values()
        ):
            raise ConfigError("environment." + key + ": expected version strings")
    technologies = require_table(raw, "technology")
    for name, tech in technologies.items():
        if not IDENTIFIER.fullmatch(name) or not isinstance(tech, dict):
            raise ConfigError("technology: expected named technology tables")
        tech.setdefault("targets", [])
        string_list(tech["targets"], "technology." + name + ".targets")
        if not isinstance(tech.get("assets", {}), dict):
            raise ConfigError("technology." + name + ".assets: expected a table")
        for asset, desc in tech.get("assets", {}).items():
            if not isinstance(desc, dict):
                raise ConfigError(
                    "technology assets require {path, sha256} descriptors"
                )
            reject_unknown(desc, {"path", "sha256"}, "technology asset " + asset)
            desc["path"] = configuration_path(project_root, desc.get("path"), asset)
            if "sha256" in desc and not re.fullmatch(r"[0-9a-f]{64}", desc["sha256"]):
                raise ConfigError("invalid asset SHA256: " + asset)
    if build["technology"] not in technologies:
        raise ConfigError("build.technology: unknown technology")
    from backends import load_backend

    flow = raw.get("flow", {})
    reject_unknown(flow, {"lint", "synth", "formal", "sim"}, "flow")
    normalized_flow = {}
    for stage, tools in flow.items():
        if not isinstance(tools, dict):
            raise ConfigError("flow." + stage + ": expected a table")
        normalized_flow[stage] = {}
        for tool, settings in tools.items():
            if not IDENTIFIER.fullmatch(tool) or not isinstance(settings, dict):
                raise ConfigError("flow entries must be named backend tables")
            settings = load_backend(project_root, stage, tool, settings)
            settings["technologies"] = string_list(
                settings.get("technologies", [build["technology"]]), "technologies"
            )
            if not settings["technologies"] or len(
                set(settings["technologies"])
            ) != len(settings["technologies"]):
                raise ConfigError("technologies: expected distinct technology names")
            for technology in settings["technologies"]:
                if technology not in technologies:
                    raise ConfigError("unknown technology: " + technology)
            normalized_flow[stage][tool] = settings
    for stage in ("lint", "synth", "formal", "sim"):
        normalized_flow.setdefault(stage, {})
    for tools in normalized_flow.values():
        for settings in tools.values():
            provider = settings.get("requires")
            if provider:
                try:
                    stage, backend = provider.split(".")
                    prerequisite = normalized_flow[stage][backend]
                except (ValueError, KeyError):
                    raise ConfigError("Unknown prerequisite flow: " + str(provider))
                if not set(settings["technologies"]) <= set(
                    prerequisite["technologies"]
                ):
                    raise ConfigError("Dependent flows require matching technologies")
    visiting, visited = set(), set()

    def visit(reference):
        if reference in visiting:
            raise ConfigError("Cyclic flow dependency: " + reference)
        if reference in visited:
            return
        visiting.add(reference)
        stage, backend = reference.split(".")
        prerequisite = normalized_flow[stage][backend].get("requires")
        if prerequisite:
            visit(prerequisite)
        visiting.remove(reference)
        visited.add(reference)

    for stage, tools in normalized_flow.items():
        for backend in tools:
            visit(stage + "." + backend)
    workflow = require_table(raw, "workflow")
    reject_unknown(workflow, {"stages"}, "workflow")
    stages = string_list(workflow.get("stages", []), "workflow.stages")
    if len(stages) != len(set(stages)):
        raise ConfigError("workflow.stages: duplicate stages")
    for stage in stages:
        if stage not in normalized_flow or not normalized_flow[stage]:
            raise ConfigError("workflow stage has no configured backend: " + stage)
    config = {
        "schema_version": 6,
        "architecture": architecture,
        "bender": bender,
        "build": build,
        "environment": environment,
        "technology": technologies,
        "flow": normalized_flow,
        "constraints": normalize_constraints(raw),
        "workflow": {"stages": stages},
    }
    from backends import invoke

    for tools in normalized_flow.values():
        for settings in tools.values():
            invoke(settings, "configure", config, settings, project_root)
    return config


def config_digest(config):
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def header(comment, digest):
    return (
        f"{comment} Generated by project_config.py; do not edit.\n"
        f"{comment} Configuration digest: {digest}\n"
    )


def render_arch_package(config, digest):
    architecture = config["architecture"]
    lines = [
        header("//", digest).rstrip(),
        "package arch_pkg;",
        "  typedef struct packed {",
        "    int unsigned xlen;",
        "    logic [63:0] reset_vector;",
        *[f"    logic has_{feature};" for feature in architecture["features"]],
        "  } arch_t;",
        "",
        f"  localparam int unsigned XLEN = 32'd{architecture['xlen']};",
        "  localparam logic [63:0] RESET_VECTOR = "
        f"64'h{architecture['reset_vector']:016x};",
        "  localparam arch_t ARCH = '{",
        "      xlen: XLEN,",
        "      reset_vector: RESET_VECTOR,",
        *[
            f"      has_{feature}: 1'b{int(architecture['features'][feature])},"
            for feature in architecture["features"]
        ],
        "      default: '0",
        "  };",
        "endpackage",
    ]
    return "\n".join(lines) + "\n"


def tcl_braced(value):
    value = str(value)
    if "{" in value or "}" in value or "\n" in value or "\r" in value:
        raise ConfigError(
            f"value cannot be represented safely in generated Tcl: {value!r}"
        )
    return "{" + value + "}"


def tcl_list(values):
    return "[list " + " ".join(tcl_braced(value) for value in values) + "]"


def format_number(value):
    return format(value, ".15g")


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


def render_outputs(config):
    digest = config_digest(config)
    return {"arch_pkg.sv": render_arch_package(config, digest)}


def generated_sources():
    return [{"include_dirs": ["."], "files": ["arch_pkg.sv"]}]


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
