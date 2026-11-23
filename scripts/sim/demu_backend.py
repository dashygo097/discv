"""DEMU platform configuration, generated firmware support and Verilator execution."""

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from project_config import (
    IDENTIFIER,
    ConfigError,
    config_digest,
    header,
    reject_unknown,
    require_string,
    unsigned_integer,
)

DEFAULT_SIM_TOP = "demu_sim_top"
PLATFORM_PACKAGE = "project/rtl/demu_platform_pkg.sv"
FIRMWARE_DIR = "project/firmware"
BAREMETAL_TEMPLATES = "sim/runtime/baremetal/rv32"
DEVICE_TYPES = {
    "tcm": "TCM",
    "boot_rom": "BootROM",
    "console": "Console",
    "host_exit": "HostExit",
}
IMAGE_MEMORY_TYPES = {"tcm", "boot_rom"}
DATA_MEMORY_TYPES = {"tcm"}

BACKEND = {
    "tool": "verilator",
    "version_args": ["--version"],
    "format": "verilator",
    "config_inputs": ["architecture", "environment.packages.spdlog"],
    "summary": "log",
    "generated_sources": [
        {"target": "simulation", "files": [PLATFORM_PACKAGE]},
    ],
    "inputs": ["sim/**/*", "build/generated/project/**/*"],
    "tracked_environment": [
        "CC",
        "CXX",
        "CFLAGS",
        "CXXFLAGS",
        "LDFLAGS",
        "CMAKE_PREFIX_PATH",
        "VERILATOR_ROOT",
    ],
    "commands": [
        [
            "cmake",
            "-S",
            "{root}/sim",
            "-B",
            "{model}",
            "-DPROJECT_CONFIG_CMAKE={inputs}/sim.cmake",
            "-DGENERATED_INCLUDE_DIR={generated}/project/include",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DOBJCACHE_ENABLED=OFF",
        ],
        ["cmake", "--build", "{model}", "--parallel", "{jobs}"],
    ],
    "outputs": {
        "compile_commands": "{model}/compile_commands.json",
        "platform": "{results}/platform.json",
    },
    "views": {"compile_commands.json": "{model}/compile_commands.json"},
    "tools": {"cmake": ["cmake", "--version"]},
    "defaults": {"threads": 1, "trace": False, "sim_top": DEFAULT_SIM_TOP},
}


def configure(config, settings, root):
    if "architecture" not in config:
        raise ConfigError("DEMU requires an architecture generator")
    if config["architecture"]["xlen"] != 32:
        raise ConfigError("DEMU currently supports 32-bit address and data words")
    section = next(
        f"flow.sim.{name}"
        for name, candidate in config["flow"]["sim"].items()
        if candidate is settings
    )
    if (
        isinstance(settings["threads"], bool)
        or not isinstance(settings["threads"], int)
        or settings["threads"] < 1
    ):
        raise ConfigError(f"{section}.threads: expected a positive integer")
    if not isinstance(settings["trace"], bool):
        raise ConfigError(f"{section}.trace: expected a boolean")
    sim_top = require_string(settings, "sim_top", section)
    if not IDENTIFIER.fullmatch(sim_top):
        raise ConfigError(
            f"{section}.sim_top: expected a SystemVerilog module identifier"
        )
    settings.update(
        normalize_simulation(
            settings,
            virt_harness=sim_top == DEFAULT_SIM_TOP,
            section=section,
        )
    )
    settings["targets"] = list(dict.fromkeys([*settings["targets"], "simulation"]))
    outputs = {
        **BACKEND["outputs"],
        **{
            role: "{results}/" + name for role, name in executable_names(config).items()
        },
    }
    if firmware_memory(config, settings) is not None:
        outputs["firmware_linker"] = "{results}/linker.ld"
        outputs["firmware_start"] = "{results}/start.S"
    settings["_backend"]["outputs"] = outputs


def executable_names(config):
    march = config["architecture"]["march"]
    return {"simulator": f"demu-sim-{march}", "simtest": f"demu-simtest-{march}"}


def host_exit_device(settings):
    return next(
        (device for device in settings["devices"] if device["type"] == "host_exit"),
        None,
    )


def firmware_memory(config, settings):
    devices = settings["devices"]
    reset_vector = config["architecture"]["reset_vector"]
    image = next(
        (device for device in devices if device.get("load_address") == reset_vector),
        None,
    )
    if image is None:
        return None

    banks = [device for device in devices if device["type"] in DATA_MEMORY_TYPES]
    data = next((bank for bank in banks if bank.get("firmware_data")), None)
    if data is None:
        candidates = [bank for bank in banks if bank is not image]
        if len(candidates) == 1:
            data = candidates[0]
        elif not candidates and image["type"] in DATA_MEMORY_TYPES:
            data = image
    return (image, data, banks) if data is not None else None


def generate(config, settings, root):
    digest = config_digest(
        {"architecture": config["architecture"], "simulation": settings}
    )
    files = {
        "project/include/demu/generated/cfg.hh": render_demu_config(config, digest),
        "project/include/demu/generated/platform.hh": render_demu_platform(
            settings, digest
        ),
        PLATFORM_PACKAGE: render_demu_platform_package(settings, digest),
    }
    memory = firmware_memory(config, settings)
    if memory is not None:
        image, data, banks = memory
        files[f"{FIRMWARE_DIR}/linker.ld"] = render_demu_linker(
            image, data, banks, digest, root
        )
        files[f"{FIRMWARE_DIR}/start.S"] = render_template(
            root / BAREMETAL_TEMPLATES / "start.S.in", {"CONFIG_DIGEST": digest}
        )
    return files


def tools(config, entry):
    return {"c++": [os.environ.get("CXX", "c++"), "--version"]}


def preflight(config, entry, root):
    if entry["settings"]["sim_top"] == DEFAULT_SIM_TOP and not config["design"]["top"]:
        raise ConfigError("The built-in DEMU harness requires design.top")
    cmake = shutil.which("cmake")
    if cmake is None:
        raise ConfigError("Required command not found: cmake")
    result = subprocess.run(
        [cmake, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )
    match = re.search(
        r"^cmake version (\d+)\.(\d+)\.(\d+)", result.stdout, re.MULTILINE
    )
    if result.returncode != 0 or match is None:
        raise ConfigError(f"Cannot determine CMake version: {cmake}")
    if tuple(map(int, match.groups())) < (3, 19, 0):
        raise ConfigError(
            f"DEMU requires CMake 3.19 or newer; found {match.group(0)} ({cmake}). "
            "Activate a newer CMake in PATH before running make sim."
        )
    if config["build"]["reproducible"] and not config["environment"]["packages"].get(
        "spdlog"
    ):
        raise ConfigError(
            "Reproducible simulation requires environment.packages.spdlog"
        )


def prepare(config, entry, root, directory, source):
    settings = entry["settings"]
    names = executable_names(config)
    values = {
        "SIM_EXECUTABLE": names["simulator"],
        "SIMTEST_EXECUTABLE": names["simtest"],
        "SIM_TOP": settings["sim_top"],
        "SIM_RTL_TOP": config["design"]["top"],
        "SIM_THREADS": settings["threads"],
        "SIM_TRACE": "ON" if settings["trace"] else "OFF",
        "SIM_BENDER_FILELIST": source,
        "SIM_SPDLOG_VERSION": config["environment"]["packages"].get("spdlog", ""),
    }
    return {
        "sim.cmake": "".join(
            f"set({key} {cmake_quote(value)})\n" for key, value in values.items()
        )
        + "set(SIM_VERILATOR_OPTIONS\n"
        + "".join(f"  {cmake_quote(option)}\n" for option in settings["options"])
        + ")\n"
    }


def collect(config, entry, directory, snapshot):
    model = directory / "model" / snapshot["input_digest"]
    results = directory / "results"
    database = model / "compile_commands.json"
    if not database.is_file():
        raise ConfigError("CMake did not create compile_commands.json")
    for name in executable_names(config).values():
        executable = model / "bin" / name
        if not executable.is_file():
            raise ConfigError(f"CMake did not create {name}")
        shutil.copy2(executable, results / name)

    architecture = config["architecture"]
    settings = entry["settings"]
    host_exit = host_exit_device(settings)
    platform = {
        "march": architecture["march"],
        "xlen": architecture["xlen"],
        "extensions": architecture["extensions"],
        "host_exit_address": None if host_exit is None else host_exit["base"],
        "reset_cycles": settings["reset_cycles"],
    }
    (results / "platform.json").write_text(json.dumps(platform, indent=2) + "\n")

    if firmware_memory(config, settings) is not None:
        firmware = Path("build/generated") / FIRMWARE_DIR
        shutil.copy2(firmware / "linker.ld", results / "linker.ld")
        shutil.copy2(firmware / "start.S", results / "start.S")


def run(config, entry, directory):
    simulation = entry["settings"]
    argv = [
        str(directory / "results" / executable_names(config)["simulator"]),
        "--cycles",
        str(simulation["max_cycles"]),
        "--reset-cycles",
        str(simulation["reset_cycles"]),
    ]
    if entry["settings"]["trace"]:
        argv.append("--trace")
    argv.extend(shlex.split(os.environ.get("SIM_ARGS", "")))
    inputs = []
    if os.environ.get("PROGRAM"):
        program = Path(os.environ["PROGRAM"]).resolve()
        if not program.is_file():
            raise ConfigError(f"Program does not exist: {program}")
        argv.append(str(program))
        inputs.append(str(program))
    return {"commands": [argv], "inputs": inputs}


def normalize_simulation(settings, *, virt_harness, section):
    simulation = {
        key: settings[key]
        for key in ("reset_cycles", "max_cycles", "ports", "devices")
        if key in settings
    }
    ports = simulation.get("ports", [])
    if not isinstance(ports, list):
        raise ConfigError(f"{section}.ports: expected an array of tables")
    normalized_ports = []
    port_names = set()
    for index, port in enumerate(ports):
        location = f"{section}.ports[{index}]"
        if not isinstance(port, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(port, {"name"}, location)
        name = require_string(port, "name", location)
        if not IDENTIFIER.fullmatch(name):
            raise ConfigError(f"{location}.name: expected an identifier")
        if name.upper() in port_names:
            raise ConfigError(f"{location}.name: duplicate port name: {name}")
        port_names.add(name.upper())
        normalized_ports.append({"name": name})

    if virt_harness and not {"IMEM", "DMEM"}.issubset(port_names):
        raise ConfigError(
            f"{section}.ports: the built-in harness requires imem and dmem"
        )

    devices = simulation.get("devices", [])
    if not isinstance(devices, list):
        raise ConfigError(f"{section}.devices: expected an array of tables")

    normalized_devices = []
    device_names = set()
    for index, device in enumerate(devices):
        location = f"{section}.devices[{index}]"
        if not isinstance(device, dict):
            raise ConfigError(f"{location}: expected a table")
        reject_unknown(
            device,
            {"name", "type", "base", "size", "load_address", "firmware_data"},
            location,
        )

        name = require_string(device, "name", location)
        if not IDENTIFIER.fullmatch(name):
            raise ConfigError(f"{location}.name: expected an identifier")
        if name in device_names:
            raise ConfigError(f"{location}.name: duplicate device name: {name}")
        device_names.add(name)

        device_type = require_string(device, "type", location)
        if device_type not in DEVICE_TYPES:
            raise ConfigError(
                f"{location}.type: expected one of {', '.join(DEVICE_TYPES)}"
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
            if device_type not in IMAGE_MEMORY_TYPES:
                raise ConfigError(
                    f"{location}.load_address: expected a memory device that can load an image"
                )
            load_address = unsigned_integer(
                device["load_address"], f"{location}.load_address"
            )
            if not base <= load_address < base + size:
                raise ConfigError(
                    f"{location}.load_address: address is outside the device"
                )
            normalized_device["load_address"] = load_address

        firmware_data = device.get("firmware_data", False)
        if not isinstance(firmware_data, bool):
            raise ConfigError(f"{location}.firmware_data: expected a boolean")
        if firmware_data:
            if device_type not in DATA_MEMORY_TYPES:
                raise ConfigError(f"{location}.firmware_data: expected writable memory")
            normalized_device["firmware_data"] = True

        normalized_devices.append(normalized_device)

    ordered_devices = sorted(normalized_devices, key=lambda device: device["base"])
    for previous, current in zip(ordered_devices, ordered_devices[1:]):
        if previous["base"] + previous["size"] > current["base"]:
            raise ConfigError(
                f"{section}.devices: overlapping address ranges: "
                f"{previous['name']} and {current['name']}"
            )

    load_devices = [device for device in normalized_devices if "load_address" in device]
    if len(load_devices) > 1:
        raise ConfigError(
            f"{section}.devices: at most one device can define load_address for PROGRAM"
        )
    if sum(device.get("firmware_data", False) for device in normalized_devices) > 1:
        raise ConfigError(
            f"{section}.devices: select at most one default firmware data bank"
        )
    if sum(device["type"] == "host_exit" for device in normalized_devices) > 1:
        raise ConfigError(
            f"{section}.devices: at most one host_exit device is supported"
        )

    return {
        "reset_cycles": unsigned_integer(
            simulation.get("reset_cycles", 5),
            f"{section}.reset_cycles",
            positive=True,
        ),
        "max_cycles": unsigned_integer(
            simulation.get("max_cycles", 1000000),
            f"{section}.max_cycles",
            maximum=0xFFFFFFFFFFFFFFFF,
        ),
        "ports": normalized_ports,
        "devices": normalized_devices,
    }


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
            for feature in architecture["features"]
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


def render_demu_platform(settings, digest):
    ports = settings["ports"]
    devices = settings["devices"]
    port_entries = [
        f"    PortDescriptor{{{cpp_string(port['name'])}}}" for port in ports
    ]
    device_entries = []
    for device in devices:
        device_entries.append(
            "    DeviceDescriptor{"
            f"{cpp_string(device['name'])}, "
            f"hal::DeviceType::{DEVICE_TYPES[device['type']]}, "
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


def render_demu_platform_package(settings, digest):
    constants = [
        f"  localparam int unsigned {port['name'].upper()}_PORT = {index};"
        for index, port in enumerate(settings["ports"])
    ]
    return (
        header("//", digest)
        + "package demu_platform_pkg;\n"
        + "\n".join(constants)
        + "\nendpackage\n"
    )


def render_demu_linker(image, data, banks, digest, root):
    origin = image["load_address"]
    image_length = image["base"] + image["size"] - origin
    image_flags = "rwx" if image["type"] in DATA_MEMORY_TYPES else "rx"
    regions = [
        f"  IMAGE ({image_flags}) : ORIGIN = 0x{origin:08X}, LENGTH = 0x{image_length:X}"
    ]
    bank_regions = {}
    data_sections, bss_sections = [], []
    copied_sections, zeroed_sections = [".data"], [".bss"]
    for bank in banks:
        name = bank["name"]
        region = "IMAGE" if bank is image else f"TCM_{name}"
        bank_regions[name] = region
        if bank is not image:
            regions.append(
                f"  {region} (rw) : ORIGIN = 0x{bank['base']:08X}, LENGTH = 0x{bank['size']:X}"
            )

        data_section = f".tcm.{name}.data"
        bss_section = f".tcm.{name}.bss"
        copied_sections.append(data_section)
        zeroed_sections.append(bss_section)
        data_sections.append(
            f"  {data_section} : ALIGN(4)\n"
            f"  {{\n    *({data_section} {data_section}.*)\n    . = ALIGN(4);\n"
            f"  }} > {region} AT > IMAGE"
        )
        bss_sections.append(
            f"  {bss_section} (NOLOAD) : ALIGN(4)\n"
            f"  {{\n    *({bss_section} {bss_section}.*)\n    . = ALIGN(4);\n"
            f"  }} > {region}"
        )

    return render_template(
        root / BAREMETAL_TEMPLATES / "linker.ld.in",
        {
            "CONFIG_DIGEST": digest,
            "MEMORY_REGIONS": "\n".join(regions),
            "DATA_REGION": bank_regions[data["name"]],
            "BANK_DATA_SECTIONS": "\n\n".join(data_sections),
            "BANK_BSS_SECTIONS": "\n\n".join(bss_sections),
            "COPY_TABLE": "\n".join(
                f"    LONG(LOADADDR({section})); LONG(ADDR({section})); LONG(SIZEOF({section}));"
                for section in copied_sections
            ),
            "ZERO_TABLE": "\n".join(
                f"    LONG(ADDR({section})); LONG(SIZEOF({section}));"
                for section in zeroed_sections
            ),
        },
    )


def render_template(path, values):
    text = path.read_text()
    for name, value in values.items():
        text = text.replace(f"@{name}@", str(value))
    unresolved = re.findall(r"@[A-Z_]+@", text)
    if unresolved:
        raise ConfigError(
            f"Unresolved template fields in {path}: {', '.join(unresolved)}"
        )
    return text
