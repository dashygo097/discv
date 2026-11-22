import json
import os
import shlex
from pathlib import Path

import lit.formats

required = (
    "STAGE_INPUT_SIMTEST",
    "STAGE_INPUT_PLATFORM",
    "STAGE_INPUT_LINKER",
    "STAGE_INPUT_START",
    "SIMTEST_CC",
    "SIMTEST_OBJCOPY",
    "SIMTEST_EXEC_ROOT",
)
if any(not os.environ.get(key) for key in required):
    lit_config.fatal("Run this suite through make simtest with a sim.demu prerequisite")

platform = json.loads(Path(os.environ["STAGE_INPUT_PLATFORM"]).read_text())
host_exit_address = lit_config.params["host_exit"]
march = platform["march"]
extensions = platform["extensions"]

config.name = f"DISCV SimTest ({march})"
config.test_format = lit.formats.ShTest(execute_external=False)
config.suffixes = [".S", ".c"]
config.test_source_root = str(Path(__file__).parent)
config.test_exec_root = os.environ["SIMTEST_EXEC_ROOT"]
if platform["xlen"] == 32 and "i" in extensions:
    config.available_features.add("rv32i")

config.substitutions.extend(
    [
        (
            "%cc",
            shlex.join(
                [
                    os.environ["SIMTEST_CC"],
                    f"-march={march}",
                    f"-DHOST_EXIT={host_exit_address}",
                    "-mabi=ilp32e" if "e" in extensions else "-mabi=ilp32",
                    "-mcmodel=medany",
                    "-O2",
                    "-ffreestanding",
                    "-nostdlib",
                    "-Wl,--no-relax",
                ]
            ),
        ),
        ("%linker_script", shlex.quote(os.environ["STAGE_INPUT_LINKER"])),
        ("%start", shlex.quote(os.environ["STAGE_INPUT_START"])),
        ("%objcopy", shlex.join([os.environ["SIMTEST_OBJCOPY"], "-O", "binary"])),
        (
            "%simtest",
            shlex.join(
                [
                    os.environ["STAGE_INPUT_SIMTEST"],
                    "--reset-cycles",
                    str(platform["reset_cycles"]),
                    "--cycles",
                    lit_config.params["max_cycles"],
                ]
            ),
        ),
    ]
)
