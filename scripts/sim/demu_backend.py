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

BACKEND = {
    "tool": "verilator",
    "version_args": ["--version"],
    "format": "verilator",
    "summary": "log",
    "generated_sources": [
        {"target": "simulation", "files": ["demu/generated/demu_platform_pkg.sv"]},
    ],
    "inputs": ["sim/**/*", "build/generated/demu/**/*"],
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
            "-DGENERATED_INCLUDE_DIR={generated}",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DOBJCACHE_ENABLED=OFF",
        ],
        ["cmake", "--build", "{model}", "--parallel", "{jobs}"],
    ],
    "outputs": ["{results}/demu-riscv", "{model}/compile_commands.json"],
    "views": {"compile_commands.json": "{model}/compile_commands.json"},
    "tools": {"cmake": ["cmake", "--version"]},
    "defaults": {"threads": 1, "trace": False},
}


def configure(config, settings, root):
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
    settings.update(
        normalize_simulation(
            settings,
            config["architecture"],
            required=True,
            section=section,
        )
    )


def generate(config, settings, root):
    digest = config_digest(config)
    return {
        "demu/generated/cfg.hh": render_demu_config(config, digest),
        "demu/generated/platform.hh": render_demu_platform(settings, digest),
        "demu/generated/demu_platform_pkg.sv": render_demu_platform_package(
            settings, digest
        ),
        "demu/linker.ld": render_demu_linker(settings, digest),
        "demu/start.S": render_demu_start(settings, digest),
    }


def tools(config, entry):
    return {"c++": [os.environ.get("CXX", "c++"), "--version"]}


def preflight(config, entry, root):
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
    values = {
        "SIM_TOP": "demu_sim_top",
        "SIM_RTL_TOP": config["architecture"]["top"],
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
    executable = model / "bin/demu-riscv"
    if not executable.is_file():
        raise ConfigError("CMake did not create the simulator executable")
    database = model / "compile_commands.json"
    if not database.is_file():
        raise ConfigError("CMake did not create compile_commands.json")
    shutil.copy2(executable, directory / "results/demu-riscv")


def run(config, entry, directory):
    if not os.environ.get("PROGRAM"):
        raise ConfigError("Use make sim-run PROGRAM=path/to/program.bin")
    program = Path(os.environ["PROGRAM"]).resolve()
    if not program.is_file():
        raise ConfigError(f"Program does not exist: {program}")
    simulation = entry["settings"]
    argv = [
        str(directory / "results/demu-riscv"),
        "--cycles",
        str(simulation["max_cycles"]),
        "--reset-cycles",
        str(simulation["reset_cycles"]),
    ]
    if entry["settings"]["trace"]:
        argv.append("--trace")
    return {
        "commands": [
            argv + shlex.split(os.environ.get("SIM_ARGS", "")) + [str(program)]
        ],
        "inputs": [str(program)],
    }


def normalize_simulation(settings, architecture, *, required, section):
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
        raise ConfigError(f"{section}.devices: expected an array of tables")

    normalized_devices = []
    device_names = set()
    load_tcm_count = 0
    for index, device in enumerate(devices):
        location = f"{section}.devices[{index}]"
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
                f"{section}.devices: overlapping address ranges: "
                f"{previous['name']} and {current['name']}"
            )

    if required:
        if not normalized_ports:
            raise ConfigError(
                f"{section}.ports: expected at least one port when simulation is enabled"
            )
        if not normalized_devices:
            raise ConfigError(
                f"{section}.devices: expected at least one device when simulation is enabled"
            )
    reset_vector = architecture["reset_vector"]
    if required and (
        isinstance(reset_vector, bool) or not isinstance(reset_vector, int)
    ):
        raise ConfigError(f"{section}: architecture.reset_vector must be an integer")
    if required:
        port_names = {port["name"] for port in normalized_ports}
        for name in ("imem", "dmem"):
            if name not in port_names:
                raise ConfigError(
                    f'{section}.ports: required virtual port is missing: "{name}"'
                )
        devices_by_name = {device["name"]: device for device in normalized_devices}
        for name in ("imem", "dmem"):
            device = devices_by_name.get(name)
            if device is None or device["type"] != "tcm":
                raise ConfigError(
                    f'{section}.devices: "{name}" must be configured with type = "tcm"'
                )

        imem = devices_by_name["imem"]
        if load_tcm_count != 1 or imem.get("load_address") != reset_vector:
            raise ConfigError(
                f"{section}.devices: imem must be the only device defining "
                "load_address, and it must equal architecture.reset_vector"
            )
        if not imem["base"] <= reset_vector < imem["base"] + imem["size"]:
            raise ConfigError(
                f"{section}.devices: architecture.reset_vector is outside imem"
            )

        host_exit_devices = [
            device for device in normalized_devices if device["type"] == "host_exit"
        ]
        if len(host_exit_devices) != 1:
            raise ConfigError(
                f"{section}.devices: exactly one host_exit device is required"
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
            positive=True,
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


def render_demu_platform_package(settings, digest):
    ports = settings["ports"]
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


def render_demu_linker(settings, digest):
    devices = {device["name"]: device for device in settings["devices"]}
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


def render_demu_start(settings, digest):
    host_exit = next(
        device for device in settings["devices"] if device["type"] == "host_exit"
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
