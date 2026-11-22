import json
import os
import sys
from pathlib import Path

CC = "riscv64-unknown-elf-gcc"
OBJCOPY = "riscv64-unknown-elf-objcopy"

BACKEND = {
    "tool": "lit",
    "script": Path(__file__).name,
    "inherit_design": False,
    "defaults": {"max_cycles": 1000000},
    "input_roles": {
        "simtest": "simtest",
        "platform": "platform",
        "linker": "firmware_linker",
        "start": "firmware_start",
    },
    "inputs": ["tests/sim/**/*"],
    "environment": {
        "SIMTEST_CC": CC,
        "SIMTEST_OBJCOPY": OBJCOPY,
        "SIMTEST_EXEC_ROOT": "{work}",
    },
    "tools": {
        CC: [CC, "--version"],
        OBJCOPY: [OBJCOPY, "--version"],
        "python": [sys.executable, "--version"],
    },
    "commands": [
        [
            sys.executable,
            "{script}",
            "-v",
            "-j",
            "{jobs}",
            "--xunit-xml-output",
            "{reports}/lit.xml",
            "{options}",
            "--param",
            "max_cycles={max_cycles}",
            "{root}/tests/sim",
        ]
    ],
    "outputs": {"lit_report": "{reports}/lit.xml"},
    "summary": "log",
}


def configure(config, settings, root):
    from project_config import unsigned_integer

    settings["max_cycles"] = unsigned_integer(
        settings["max_cycles"],
        "flow.simtest.lit.max_cycles",
        positive=True,
        maximum=0xFFFFFFFFFFFFFFFF,
    )


def main(args):
    platform = json.loads(Path(os.environ["STAGE_INPUT_PLATFORM"]).read_text())
    host_exit = platform["host_exit_address"]
    if host_exit is None:
        raise SystemExit("The simtest prerequisite must configure a host_exit device")
    os.execvp("lit", ["lit", *args, "--param", f"host_exit={host_exit:#x}"])


if __name__ == "__main__":
    main(sys.argv[1:])
