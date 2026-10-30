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
MICROARCHITECTURE_CAPABILITIES = {
    "cpu_5stage_top": {
        "xlen": 32,
        "extensions": frozenset({"i"}),
    },
}


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


def validate_microarchitecture(top, xlen, extensions):
    capability = MICROARCHITECTURE_CAPABILITIES.get(top)
    if capability is None:
        known = ", ".join(sorted(MICROARCHITECTURE_CAPABILITIES))
        raise ConfigError(
            f"architecture.top: no capability contract is registered for {top}; "
            f"known microarchitectures: {known}"
        )
    if xlen != capability["xlen"]:
        raise ConfigError(
            f"architecture.march: {top} supports RV{capability['xlen']}, "
            f"but RV{xlen} was requested"
        )
    unsupported = sorted(extensions - capability["extensions"])
    missing = sorted(capability["extensions"] - extensions)
    if unsupported or missing:
        details = []
        if unsupported:
            details.append(f"unsupported extension(s): {', '.join(unsupported)}")
        if missing:
            details.append(f"required extension(s) missing: {', '.join(missing)}")
        raise ConfigError(
            f"architecture.march: {top} does not support the requested ISA "
            f"({'; '.join(details)})"
        )


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


def normalize_simulation(raw, architecture, *, required):
    simulation = raw.get("simulation", {})
    if not isinstance(simulation, dict):
        raise ConfigError("simulation: expected a table")
    reject_unknown(
        simulation,
        {"reset_cycles", "max_cycles", "ports", "devices"},
        "simulation",
    )

    ports = simulation.get("ports", [])
    if not isinstance(ports, list):
        raise ConfigError("simulation.ports: expected an array of tables")
    normalized_ports = []
    port_names = set()
    for index, port in enumerate(ports):
        location = f"simulation.ports[{index}]"
        if not isinstance(port, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(port, {"name", "protocol"}, location)
        name = require_string(port, "name", location)
        if not IDENTIFIER.match(name):
            raise ConfigError(f"{location}.name: expected an identifier")
        if name in port_names:
            raise ConfigError(f"{location}.name: duplicate port name: {name}")
        port_names.add(name)
        protocol = require_string(port, "protocol", location)
        if protocol != "virt":
            raise ConfigError(
                f'{location}.protocol: only "virt" is currently implemented'
            )
        normalized_ports.append(
            {
                "name": name,
                "protocol": protocol,
            }
        )

    devices = simulation.get("devices", [])
    if not isinstance(devices, list):
        raise ConfigError("simulation.devices: expected an array of tables")

    normalized_devices = []
    device_names = set()
    load_tcm_count = 0
    for index, device in enumerate(devices):
        location = f"simulation.devices[{index}]"
        if not isinstance(device, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(
            device,
            {"name", "type", "base", "size", "load_address"},
            location,
        )

        name = require_string(device, "name", location)
        if not IDENTIFIER.match(name):
            raise ConfigError(f"{location}.name: expected an identifier")
        if name in device_names:
            raise ConfigError(f"{location}.name: duplicate device name: {name}")
        device_names.add(name)

        device_type = require_string(device, "type", location)
        if device_type not in {"tcm", "console", "host_exit"}:
            raise ConfigError(
                f'{location}.type: expected "tcm", "console", or "host_exit"'
            )
        base = unsigned_integer(device.get("base"), f"{location}.base")
        size = unsigned_integer(device.get("size"), f"{location}.size", positive=True)
        if base + size > 0x100000000:
            raise ConfigError(f"{location}: device range exceeds 32-bit address space")

        normalized_device = {
            "name": name,
            "type": device_type,
            "base": base,
            "size": size,
        }
        if "load_address" in device:
            if device_type != "tcm":
                raise ConfigError(
                    f"{location}.load_address: only TCM devices can define a load address"
                )
            load_address = unsigned_integer(
                device["load_address"], f"{location}.load_address"
            )
            if not base <= load_address < base + size:
                raise ConfigError(
                    f"{location}.load_address: address is outside the device"
                )
            normalized_device["load_address"] = load_address
            load_tcm_count += 1

        normalized_devices.append(normalized_device)

    ordered_devices = sorted(normalized_devices, key=lambda device: device["base"])
    for previous, current in zip(ordered_devices, ordered_devices[1:]):
        if previous["base"] + previous["size"] > current["base"]:
            raise ConfigError(
                "simulation.devices: overlapping address ranges: "
                f"{previous['name']} and {current['name']}"
            )

    if required:
        if not normalized_ports:
            raise ConfigError(
                "simulation.ports: expected at least one port when simulation is enabled"
            )
        if not normalized_devices:
            raise ConfigError(
                "simulation.devices: expected at least one device when simulation is enabled"
            )
    reset_vector = architecture["reset_vector"]
    if required and (
        isinstance(reset_vector, bool) or not isinstance(reset_vector, int)
    ):
        raise ConfigError("simulation: architecture.reset_vector must be an integer")
    if required:
        port_names = {port["name"] for port in normalized_ports}
        for name in ("imem", "dmem"):
            if name not in port_names:
                raise ConfigError(
                    f'simulation.ports: required virtual port is missing: "{name}"'
                )
        devices_by_name = {device["name"]: device for device in normalized_devices}
        for name in ("imem", "dmem"):
            device = devices_by_name.get(name)
            if device is None or device["type"] != "tcm":
                raise ConfigError(
                    f'simulation.devices: "{name}" must be configured with type = "tcm"'
                )

        imem = devices_by_name["imem"]
        if load_tcm_count != 1 or imem.get("load_address") != reset_vector:
            raise ConfigError(
                "simulation.devices: imem must be the only device defining "
                "load_address, and it must equal architecture.reset_vector"
            )
        if not imem["base"] <= reset_vector < imem["base"] + imem["size"]:
            raise ConfigError(
                "simulation.devices: architecture.reset_vector is outside imem"
            )

        host_exit_devices = [
            device for device in normalized_devices if device["type"] == "host_exit"
        ]
        if len(host_exit_devices) != 1:
            raise ConfigError(
                "simulation.devices: exactly one host_exit device is required"
            )

    return {
        "reset_cycles": unsigned_integer(
            simulation.get("reset_cycles", 5),
            "simulation.reset_cycles",
            positive=True,
        ),
        "max_cycles": unsigned_integer(
            simulation.get("max_cycles", 1000000),
            "simulation.max_cycles",
            positive=True,
            maximum=0xFFFFFFFFFFFFFFFF,
        ),
        "ports": normalized_ports,
        "devices": normalized_devices,
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
            "simulation",
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
    validate_microarchitecture(top, xlen, extensions)
    architecture = dict(
        architecture,
        xlen=xlen,
        extensions=sorted(extensions),
        features={feature: feature in extensions for feature in ARCH_FEATURES},
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
    return {
        "schema_version": 6,
        "architecture": architecture,
        "bender": bender,
        "build": build,
        "environment": environment,
        "technology": technologies,
        "flow": normalized_flow,
        "constraints": normalize_constraints(raw),
        "simulation": normalize_simulation(
            raw, architecture, required=bool(normalized_flow["sim"])
        ),
        "workflow": {"stages": stages},
    }


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
        *[f"    logic has_{feature};" for feature in ARCH_FEATURES],
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
            for feature in ARCH_FEATURES
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


def cmake_quote(value):
    value = str(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cpp_string(value):
    return json.dumps(str(value), ensure_ascii=True)


def render_demu_config(config, digest):
    architecture = config["architecture"]
    values = [
        f"inline constexpr std::string_view MARCH = {cpp_string(architecture['march'])};",
        f"inline constexpr std::uint64_t XLEN = UINT64_C({architecture['xlen']});",
        "inline constexpr std::uint64_t RESET_VECTOR = "
        f"UINT64_C({architecture['reset_vector']});",
        *[
            f"inline constexpr bool HAS_{feature.upper()} = "
            f"{'true' if architecture['features'][feature] else 'false'};"
            for feature in ARCH_FEATURES
        ],
    ]

    return "".join(
        [
            header("//", digest),
            "#pragma once\n\n",
            "#include <cstdint>\n",
            "#include <string_view>\n",
            "\nnamespace demu::generated {\n\n",
            "\n".join(values),
            "\n\n} // namespace demu::generated\n",
        ]
    )


def render_demu_platform(config, digest):
    simulation = config["simulation"]
    ports = simulation["ports"]
    devices = simulation["devices"]
    type_names = {
        "tcm": "TCM",
        "console": "Console",
        "host_exit": "HostExit",
    }
    port_entries = []
    for port in ports:
        port_entries.append(
            f"    PortDescriptor{{{cpp_string(port['name'])}, hal::BusProtocol::Virt}}"
        )
    device_entries = []
    for device in devices:
        device_entries.append(
            "    DeviceDescriptor{"
            f"{cpp_string(device['name'])}, "
            f"hal::DeviceType::{type_names[device['type']]}, "
            f"UINT64_C({device['base']}), UINT64_C({device['size']}), "
            f"{'true' if 'load_address' in device else 'false'}, "
            f"UINT64_C({device.get('load_address', 0)})"
            "}"
        )
    return "".join(
        [
            header("//", digest),
            "#pragma once\n\n",
            '#include "demu/hal/platform.hh"\n',
            "#include <array>\n",
            "#include <cstdint>\n",
            "\nnamespace demu::generated {\n\n",
            "using hal::DeviceDescriptor;\n\n",
            "using hal::PortDescriptor;\n\n",
            f"inline constexpr std::array<PortDescriptor, {len(ports)}> PORTS{{{{\n",
            ",\n".join(port_entries),
            "\n}};\n\n",
            f"inline constexpr std::array<DeviceDescriptor, {len(devices)}> DEVICES{{{{\n",
            ",\n".join(device_entries),
            "\n}};\n\n",
            "} // namespace demu::generated\n",
        ]
    )


def render_demu_platform_package(config, digest):
    ports = config["simulation"]["ports"]
    port_constants = [
        f"  localparam int unsigned {port['name'].upper()}_PORT = {index};"
        for index, port in enumerate(ports)
    ]
    return "".join(
        [
            header("//", digest),
            "package demu_platform_pkg;\n\n",
            "\n".join(port_constants),
            "\n",
            "endpackage\n",
        ]
    )


def render_demu_linker(config, digest):
    devices = {device["name"]: device for device in config["simulation"]["devices"]}
    imem = devices["imem"]
    dmem = devices["dmem"]
    imem_origin = imem["load_address"]
    imem_length = imem["base"] + imem["size"] - imem_origin

    return "".join(
        [
            "/* Generated by project_config.py; do not edit.\n",
            f" * Configuration digest: {digest}\n",
            " */\n",
            "OUTPUT_ARCH(riscv)\n",
            "ENTRY(_start)\n\n",
            "MEMORY\n",
            "{\n",
            f"  IMEM (rx)  : ORIGIN = 0x{imem_origin:08X}, LENGTH = 0x{imem_length:X}\n",
            f"  DMEM (rw)  : ORIGIN = 0x{dmem['base']:08X}, LENGTH = 0x{dmem['size']:X}\n",
            "}\n\n",
            "SECTIONS\n",
            "{\n",
            "  .text :\n",
            "  {\n",
            "    KEEP(*(.text.start))\n",
            "    *(.text .text.*)\n",
            "  } > IMEM\n\n",
            "  .rodata :\n",
            "  {\n",
            "    *(.rodata .rodata.*)\n",
            "    *(.srodata .srodata.*)\n",
            "    *(.eh_frame .eh_frame.*)\n",
            "  } > IMEM\n\n",
            "  .data :\n",
            "  {\n",
            "    . = ALIGN(4);\n",
            "    __data_start = .;\n",
            "    *(.data .data.*)\n",
            "    *(.sdata .sdata.*)\n",
            "    . = ALIGN(4);\n",
            "    __data_end = .;\n",
            "  } > DMEM AT > IMEM\n",
            "  __data_load_start = LOADADDR(.data);\n",
            "  PROVIDE(__global_pointer$ = __data_start + 0x800);\n\n",
            "  .bss (NOLOAD) :\n",
            "  {\n",
            "    . = ALIGN(4);\n",
            "    __bss_start = .;\n",
            "    *(.bss .bss.*)\n",
            "    *(.sbss .sbss.*)\n",
            "    *(COMMON)\n",
            "    . = ALIGN(4);\n",
            "    __bss_end = .;\n",
            "  } > DMEM\n\n",
            "  . = ALIGN(16);\n",
            "  __heap_start = .;\n",
            "  __stack_top = (ORIGIN(DMEM) + LENGTH(DMEM)) & ~15;\n",
            "  __heap_end = __stack_top;\n",
            '  ASSERT(__heap_start <= __stack_top, "DMEM overflow")\n\n',
            "  /DISCARD/ :\n",
            "  {\n",
            "    *(.comment)\n",
            "    *(.note .note.*)\n",
            "  }\n",
            "}\n",
        ]
    )


def render_demu_start(config, digest):
    host_exit = next(
        device
        for device in config["simulation"]["devices"]
        if device["type"] == "host_exit"
    )
    return "".join(
        [
            header("//", digest),
            '.section .text.start, "ax", @progbits\n',
            ".align 2\n",
            ".globl _start\n",
            ".type _start, @function\n\n",
            "_start:\n",
            "  .option push\n",
            "  .option norelax\n",
            "  la gp, __global_pointer$\n",
            "  .option pop\n",
            "  la sp, __stack_top\n\n",
            "  la t0, __data_load_start\n",
            "  la t1, __data_start\n",
            "  la t2, __data_end\n",
            ".Lcopy_data:\n",
            "  bgeu t1, t2, .Lclear_bss_begin\n",
            "  lw t3, 0(t0)\n",
            "  sw t3, 0(t1)\n",
            "  addi t0, t0, 4\n",
            "  addi t1, t1, 4\n",
            "  j .Lcopy_data\n\n",
            ".Lclear_bss_begin:\n",
            "  la t0, __bss_start\n",
            "  la t1, __bss_end\n",
            ".Lclear_bss:\n",
            "  bgeu t0, t1, .Lcall_main\n",
            "  sw zero, 0(t0)\n",
            "  addi t0, t0, 4\n",
            "  j .Lclear_bss\n\n",
            ".Lcall_main:\n",
            "  call main\n",
            f"  li t0, 0x{host_exit['base']:08X}\n",
            "  sw a0, 0(t0)\n",
            ".Lhalt:\n",
            "  j .Lhalt\n\n",
            ".size _start, . - _start\n",
        ]
    )


def render_outputs(config, config_path, project_root, output_dir):
    digest = config_digest(config)
    outputs = {"arch_pkg.sv": render_arch_package(config, digest)}
    if config["flow"]["synth"]:
        outputs["constraints.sdc"] = render_constraints_sdc(config, digest)
    if config["flow"]["sim"]:
        outputs.update(
            {
                "demu/generated/cfg.hh": render_demu_config(config, digest),
                "demu/generated/platform.hh": render_demu_platform(config, digest),
                "demu/generated/demu_platform_pkg.sv": render_demu_platform_package(
                    config, digest
                ),
                "demu/linker.ld": render_demu_linker(config, digest),
                "demu/start.S": render_demu_start(config, digest),
            }
        )
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
