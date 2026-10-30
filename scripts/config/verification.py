"""Integration checks exercised through the same public Make entry as real builds."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from project_config import ConfigError


def verify(repository):
    def require(condition, message):
        if not condition:
            raise ConfigError("Integration check failed: " + message)

    with tempfile.TemporaryDirectory(prefix="discv-bender-check-") as temporary:
        root = Path(temporary).resolve()
        shutil.copytree(
            repository / "scripts",
            root / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copyfile(repository / "Makefile", root / "Makefile")
        # Reuse the already bootstrapped interpreter without network access.
        (root / "build").mkdir()
        (root / "build/.venv").symlink_to(
            repository / "build/.venv", target_is_directory=True
        )
        (root / ".gitignore").write_text("build/\n.bender/\nBender.yml\n")
        (root / "rtl").mkdir()
        (root / "include").mkdir()
        (root / "include/value.svh").write_text("`define VALUE 1'b0\n")
        (root / "rtl/cpu.sv").write_text(
            '`include "value.svh"\nmodule cpu_5stage_top(input logic a, output logic y);\n'
            "  technology_cell u_cell(.a(a ^ `VALUE), .y(y));\nendmodule\n"
        )
        (root / "alpha.sv").write_text(
            "module technology_cell(input logic a, output logic y); assign y = a; endmodule\n"
        )
        (root / "beta.sv").write_text(
            "module technology_cell(input logic a, output logic y); assign y = ~a; endmodule\n"
        )
        (root / "excluded.sv").write_text("THIS MUST NEVER BE COMPILED\n")
        config = """schema_version = 6
[architecture]
march = "rv32i"
top = "cpu_5stage_top"
reset_vector = 0
[bender]
name = "integration"
version = "0.32.1"
dependencies = {}
[[bender.sources]]
include_dirs = ["include"]
files = ["rtl/*.sv"]
[[bender.sources]]
target = "alpha"
files = ["alpha.sv"]
[[bender.sources]]
target = "beta"
files = ["beta.sv"]
[[bender.sources]]
target = "never"
files = ["excluded.sv"]
[build]
jobs = 2
technology = "alpha"
[technology.alpha]
targets = ["alpha"]
[technology.beta]
targets = ["beta"]
[flow.lint.verilator]
technologies = ["alpha", "beta"]
options = ["-Wno-fatal"]
[workflow]
stages = ["lint"]
"""
        project = root / "Project.toml"
        project.write_text(config)

        def make(goal, passed=True):
            command = ["make", "--no-print-directory", goal]
            result = subprocess.run(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            require((result.returncode == 0) == passed, goal + "\n" + result.stdout)
            return result

        def snapshots():
            return {
                json.loads(path.read_text())["entry"]["id"]: json.loads(
                    path.read_text()
                )
                for path in (root / "build/generated/flows/lint").rglob("inputs.json")
            }

        def stamps():
            return {
                str(path): path.stat().st_mtime_ns
                for path in (root / "build/lint").rglob(".done")
            }

        make("workflow")
        first = stamps()
        require(
            len(first) == 2,
            "technology matrix must produce two distinct successful runs",
        )
        lock_before = (root / "Bender.lock").read_bytes()
        make("lint")
        require(stamps() == first, "unchanged workflow must be a no-op")
        header = root / "include/value.svh"
        stat = header.stat()
        header.write_text("`define VALUE 1'b1\n")
        os.utime(header, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        make("lint")
        require(
            all(stamps()[path] != old for path, old in first.items()),
            "header content changes must rebuild even with restored mtime",
        )
        addition = root / "rtl/added.sv"
        addition.write_text("module added; endmodule\n")
        make("lint")
        require(
            all(
                any(str(addition) in group["files"] for group in snapshot["sources"])
                for snapshot in snapshots().values()
            ),
            "new glob match must be discovered",
        )
        addition.unlink()
        make("lint")
        require(
            all(
                all(
                    str(addition) not in group["files"] for group in snapshot["sources"]
                )
                for snapshot in snapshots().values()
            ),
            "deleted glob match must disappear",
        )
        stamp = next((root / "build/lint").rglob(".done"))
        report = stamp.parent / "reports/summary.rpt"
        report.unlink()
        previous = stamp.stat().st_mtime_ns
        make("lint")
        require(
            report.exists() and stamp.stat().st_mtime_ns != previous,
            "deleted output must invalidate the cache",
        )
        require(
            (root / "Bender.lock").read_bytes() == lock_before,
            "ordinary builds must preserve the dependency lock",
        )

        # A real frontend failure must remove every affected success stamp and
        # retain a failure record rather than accepting stale reports.
        source = root / "rtl/cpu.sv"
        original = source.read_text()
        source.write_text("this is invalid SystemVerilog\n")
        make("lint", passed=False)
        require(not stamps(), "failed lint must not leave success stamps")
        failures = list((root / "build/lint").rglob("run.json"))
        require(
            all(
                json.loads(path.read_text())["status"] == "failed" for path in failures
            ),
            "failed stages must retain failed execution records",
        )
        source.write_text(original)
        make("lint")

        project.write_text(
            config.replace(
                'options = ["-Wno-fatal"]',
                'options = ["-Wno-fatal"]\nversion = "INTENTIONALLY_WRONG_VERSION"',
            )
        )
        make("lint", passed=False)
        project.write_text(config)
        make("lint")

        # Local package fixture: Bender owns resolution; normal builds cannot
        # silently introduce new packages or change the locked declaration.
        package = root / "ip"
        package.mkdir()
        (package / "Bender.yml").write_text(
            "package:\n  name: local_ip\nsources:\n  - ip.sv\n"
        )
        (package / "ip.sv").write_text("module dependency_ip; endmodule\n")
        project.write_text(
            config.replace(
                "dependencies = {}", 'dependencies = {local_ip = {path = "ip"}}'
            )
        )
        make("lint", passed=False)
        require(
            (root / "Bender.lock").read_bytes() == lock_before,
            "rejected dependency change must preserve lock",
        )
        make("deps-update")
        make("lint")
        require(
            any(
                "local_ip" in snapshot["packages"] for snapshot in snapshots().values()
            ),
            "native local dependency must be present in provenance",
        )
        (root / "Bender.local").write_text("overrides: {}\n")
        make("config", passed=False)
        (root / "Bender.local").unlink()

        # Add a backend implementation and two script variants without changing
        # any common driver code. This executes real Tcl, not a mocked DC run.
        implementation = root / "scripts/synth/tclprobe_backend.py"
        version = root / "version.tcl"
        version.write_text("puts [info patchlevel]\n")
        implementation.write_text(
            "BACKEND = "
            + repr(
                {
                    "tool": "tclsh",
                    "version_args": [str(version)],
                    "format": "synopsys",
                    "commands": [["tclsh", "{script}"]],
                    "outputs": ["{results}/proof.txt", "{reports}/summary.rpt"],
                }
            )
            + "\n"
        )
        for name in ("first", "second"):
            (root / (name + ".tcl")).write_text(
                "source $::env(STAGE_CONFIG)\n"
                "set output [open [file join $::env(STAGE_RESULT_DIR) proof.txt] w]\n"
                "puts $output [list " + name + " [dict get $PROJECT flow custom_knob] "
                "[dict get $PROJECT technology marker]]\nclose $output\n"
                "set report [open [file join $::env(STAGE_REPORT_DIR) summary.rpt] w]\n"
                "puts $report PASS\nclose $report\n"
            )
        variants = config.replace(
            'targets = ["alpha"]\n[technology.beta]',
            'targets = ["alpha"]\nmarker = "alpha-value"\n[technology.beta]',
        ).replace(
            'targets = ["beta"]\n[flow.lint',
            'targets = ["beta"]\nmarker = "beta-value"\n[flow.lint',
        )
        variants += """
[flow.synth.first]
backend = "tclprobe"
script = "first.tcl"
technologies = ["alpha", "beta"]
custom_knob = "from-golden-config"
[flow.synth.second]
backend = "tclprobe"
script = "second.tcl"
technologies = ["alpha", "beta"]
custom_knob = "from-golden-config"
"""
        project.write_text(variants)
        make("deps-update")
        make("synth")
        proofs = list((root / "build/synth").rglob("proof.txt"))
        require(
            len(proofs) == 4,
            "two scripts by two technologies must produce four isolated results",
        )
        require(
            {path.read_text().strip() for path in proofs}
            == {
                f"{script} from-golden-config {technology}-value"
                for script in ("first", "second")
                for technology in ("alpha", "beta")
            },
            "custom backend settings and technology fields must reach the selected Tcl script",
        )
        before = {
            str(path): path.stat().st_mtime_ns
            for path in (root / "build/synth").rglob(".done")
        }
        make("synth")
        require(
            all(
                Path(path).stat().st_mtime_ns == stamp for path, stamp in before.items()
            ),
            "script/technology variants must also cache correctly",
        )

        # Check actual DC/Formality source projection and prerequisite wiring,
        # without claiming to execute unavailable licensed EDA tools.
        variants += """
[technology.alpha.dc]
target_libraries = ["slow.db"]
[flow.synth.dc]
technologies = ["alpha"]
targets = ["synthesis"]
[flow.formal.formality]
technologies = ["alpha"]
"""
        project.write_text(variants)
        make("config")
        graph = (root / "build/generated/build.mk").read_text()
        formal = next((root / "build/generated/flows/formal").rglob("inputs.json"))
        dc = next((root / "build/generated/flows/synth/alpha/dc").rglob("inputs.json"))
        require(
            json.loads(formal.read_text())["sources"]
            == json.loads(dc.read_text())["sources"],
            "Formality reference and DC must resolve identical source groups/defines",
        )
        formal_id = json.loads(formal.read_text())["entry"]["id"]
        dc_id = json.loads(dc.read_text())["entry"]["id"]
        rule = next(
            line
            for line in graph.splitlines()
            if line.startswith(str(root / "build" / formal_id / ".done") + ":")
        )
        require(
            str(root / "build" / dc_id / ".done") in rule,
            "Formality must depend on the matching DC artifact stamp",
        )
        print(
            "[CHECK] PASS: technology matrix, target isolation, no-op rebuild, header content, "
            "source add/delete, output recovery, failure records, version enforcement, frozen lock, "
            "explicit dependency update, local package provenance, backend discovery, "
            "script/technology variants, arbitrary Tcl parameters, DC/Formality wiring"
        )
    return 0
