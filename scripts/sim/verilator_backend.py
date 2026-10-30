"""DEMU build/run integration using native Bender Verilator inputs."""

import os
import shlex
import shutil
from pathlib import Path

from project_config import ConfigError, cmake_quote

BACKEND = {
    "tool": "verilator",
    "version_args": ["--version"],
    "format": "verilator",
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
    "outputs": ["{results}/demu-riscv"],
    "tools": {"cmake": ["--version"], "c++": ["--version"]},
    "defaults": {"threads": 1, "trace": False},
}


def prepare(config, entry, root, directory, source):
    settings = entry["settings"]
    if not isinstance(settings["threads"], int) or settings["threads"] < 1:
        raise ConfigError("simulation threads must be positive")
    if not isinstance(settings["trace"], bool):
        raise ConfigError("simulation trace must be boolean")
    values = {
        "SIM_PROJECT_ROOT": root,
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
    executable = directory / "model" / snapshot["input_digest"] / "bin/demu-riscv"
    if not executable.is_file():
        raise ConfigError("CMake did not create the simulator executable")
    shutil.copy2(executable, directory / "results/demu-riscv")


def run(config, entry, directory):
    if not os.environ.get("PROGRAM"):
        raise ConfigError("Use make sim-run PROGRAM=path/to/program.bin")
    program = Path(os.environ["PROGRAM"]).resolve()
    if not program.is_file():
        raise ConfigError(f"Program does not exist: {program}")
    simulation = config["simulation"]
    argv = [
        str(directory / "results/demu-riscv"),
        "--cycles",
        str(simulation["max_cycles"]),
        "--reset-cycles",
        str(simulation["reset_cycles"]),
    ]
    if entry["settings"]["trace"]:
        argv.append("--trace")
    return argv + shlex.split(os.environ.get("SIM_ARGS", "")) + [str(program)]
