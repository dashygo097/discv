"""Single project driver, called by Make. Bender owns HDL/package resolution."""

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import bender
from backends import (
    commands,
    configuration_tcl,
    declared_outputs,
    invoke,
    technology_inputs,
)
from project_config import (
    ConfigError,
    atomic_write,
    config_digest,
    load_config,
    render_outputs,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "build/generated"


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def tool_identity(command, arguments):
    executable = shutil.which(command)
    if executable is None:
        return {"command": command, "available": False}
    try:
        result = subprocess.run(
            [executable, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise ConfigError("Timed out querying tool version: " + command)
    return {
        "command": command,
        "available": True,
        "path": str(Path(executable).resolve()),
        "executable_sha256": sha256(Path(executable)),
        "version": result.stdout.strip(),
        "version_exit_code": result.returncode,
    }


def entries(config):
    result = []
    for stage, tools in config["flow"].items():
        for tool, settings in tools.items():
            for technology in settings["technologies"]:
                result.append(
                    {
                        "id": stage
                        + "/"
                        + technology
                        + "/"
                        + tool
                        + "/"
                        + config_digest(config)[:12],
                        "stage": stage,
                        "tool": tool,
                        "technology": technology,
                        "settings": settings,
                    }
                )
    return result


def provider_for(config, entry):
    reference = entry["settings"].get("requires")
    if not reference:
        return None
    stage, tool = reference.split(".")
    return dict(
        entry,
        stage=stage,
        tool=tool,
        settings=config["flow"][stage][tool],
        id="/".join((stage, entry["technology"], tool, config_digest(config)[:12])),
    )


def targets_for(config, entry):
    provider = provider_for(config, entry)
    if provider:
        return targets_for(config, provider)
    return list(
        dict.fromkeys(
            config["technology"][entry["technology"]]["targets"]
            + entry["settings"]["targets"]
        )
    )


def inputs_for(config, entry, groups):
    files = set()
    for group in groups:
        files.update(Path(file) for file in group["files"])
        # Header inventory is for invalidation/provenance only. Bender exclusively
        # decides compilation sources, include scopes, defines and ordering.
        for directory in group["include_dirs"]:
            files.update(
                file
                for file in Path(directory).rglob("*")
                if file.is_file()
                and file.suffix.lower() in (".svh", ".vh", ".h", ".hh", ".hpp")
            )
    files.update((ROOT / "scripts/config").glob("*.py"))
    files.add(Path(entry["settings"]["_backend"]["definition"]))
    if entry["settings"].get("script"):
        files.add(Path(entry["settings"]["script"]))
    for pattern in entry["settings"].get("inputs", []):
        matches = [path for path in ROOT.glob(pattern) if path.is_file()]
        if not matches:
            raise ConfigError("Declared input matched no files: " + pattern)
        files.update(matches)
    files.add(ROOT / "Project.toml")
    # The native manifest is a projection, not another independent input.
    # Its semantic content is already in config and the resolved Bender groups.
    files.add(ROOT / "Bender.lock")
    if entry["stage"] == "sim":
        files.update(file for file in (ROOT / "sim").rglob("*") if file.is_file())
        files.update(file for file in (GENERATED / "demu").rglob("*") if file.is_file())
    technology = config["technology"][entry["technology"]]
    selectors = entry["settings"]["_backend"].get("technology_inputs", [])
    for path in technology_inputs(technology, selectors):
        files.add(Path(path) if Path(path).is_absolute() else ROOT / path)
    if (GENERATED / "constraints.sdc").is_file():
        files.add(GENERATED / "constraints.sdc")
    files.update(Path(asset["path"]) for asset in technology.get("assets", {}).values())
    return {
        str(path): sha256(path) if path.is_file() else None for path in sorted(files)
    }


def stage_path(entry):
    return ROOT / "build" / entry["id"]


def artifact_paths(config, entry):
    snapshot = json.loads(
        (GENERATED / "flows" / entry["id"] / "inputs.json").read_text()
    )
    return declared_outputs(
        config,
        entry,
        ROOT,
        stage_path(entry),
        GENERATED / "flows" / entry["id"],
        snapshot["input_digest"],
    )


def check_cached_outputs(config, entry, input_digest):
    directory = stage_path(entry)
    stamp = directory / ".done"
    if not stamp.exists():
        return
    run = directory / "run.json"
    try:
        record = json.loads(run.read_text())
        valid = (
            record["status"] == "passed"
            and record["inputs"]["input_digest"] == input_digest
            and stamp.read_text().strip() == input_digest
            and record["artifacts"]
            and all(
                Path(path).is_file() and sha256(Path(path)) == digest
                for path, digest in record["artifacts"].items()
            )
        )
    except (OSError, ValueError, KeyError):
        valid = False
    if not valid:
        stamp.unlink()


def prepare(config, update=False):
    provenance = bender.resolve(config, ROOT, update)
    generated = render_outputs(config, ROOT / "Project.toml", ROOT, GENERATED)
    for name, content in generated.items():
        atomic_write(GENERATED / name, content)
    # Remove only known obsolete projections from the previous architecture.
    for name in (
        "rtl.f",
        "rtl.tcl",
        "project.mk",
        "project.env",
        "sim.cmake",
        "synth.dc.tcl",
        ".done",
    ):
        path = GENERATED / name
        if path.is_file():
            path.unlink()
    package_state = bender.packages(ROOT, config["build"]["reproducible"])
    effective_environment = {
        name: os.environ.get(name)
        for name in set(config["environment"]["required_variables"])
        | {
            "PATH",
            "CC",
            "CXX",
            "CFLAGS",
            "CXXFLAGS",
            "LDFLAGS",
            "CMAKE_PREFIX_PATH",
            "VERILATOR_ROOT",
            "LC_ALL",
            "LANG",
            "TZ",
            "SOURCE_DATE_EPOCH",
        }
    }
    resolved = entries(config)
    make_lines = [
        ".DELETE_ON_ERROR:",
        ".PHONY: lint synth formal sim sim-run workflow",
        ".DEFAULT_GOAL := workflow",
    ]
    by_stage = {stage: [] for stage in config["flow"]}
    snapshots = {}
    for entry in resolved:
        directory = GENERATED / "flows" / entry["id"]
        directory.mkdir(parents=True, exist_ok=True)
        active_targets = targets_for(config, entry)
        groups = bender.sources(ROOT, active_targets)
        export = bender.export(
            ROOT, active_targets, entry["settings"]["_backend"]["format"]
        )
        script = directory / (
            "sources.tcl" if entry["stage"] in ("synth", "formal") else "sources.f"
        )
        atomic_write(script, export)
        for name, content in (
            invoke(entry, "prepare", config, entry, ROOT, directory, script) or {}
        ).items():
            atomic_write(directory / name, content)
        if entry["stage"] in ("synth", "formal"):
            atomic_write(directory / "backend.tcl", configuration_tcl(config, entry))
        backend = entry["settings"]["_backend"]
        tools = {
            backend["tool"]: tool_identity(backend["tool"], backend["version_args"])
        }
        for tool, arguments in backend.get("tools", {}).items():
            tools[tool] = tool_identity(
                os.environ.get("CXX", tool) if tool == "c++" else tool, arguments
            )
        snapshot = {
            "entry": entry,
            "configuration": config,
            "configuration_digest": config_digest(config),
            "bender": provenance,
            "packages": package_state,
            "targets": active_targets,
            "sources": groups,
            "tools": tools,
            "environment": effective_environment,
            "files": inputs_for(config, entry, groups),
            "generated": {
                name: hashlib.sha256(content.encode()).hexdigest()
                for name, content in generated.items()
            },
            "exports": {
                str(path): sha256(path)
                for path in directory.iterdir()
                if path.name in ("sources.f", "sources.tcl", "backend.tcl", "sim.cmake")
            },
            "export_contents": {
                str(path): path.read_text()
                for path in directory.iterdir()
                if path.name in ("sources.f", "sources.tcl", "backend.tcl", "sim.cmake")
            },
        }
        snapshot["input_digest"] = bender.digest(snapshot)
        snapshot_path = directory / "inputs.json"
        write_json(snapshot_path, snapshot)
        snapshots[entry["id"]] = snapshot
        stamp = stage_path(entry) / ".done"
        check_cached_outputs(config, entry, snapshot["input_digest"])
        dependency = ""
        provider = provider_for(config, entry)
        if provider:
            dependency = str(stage_path(provider) / ".done")
        # Dependencies are content inventories refreshed before Make is invoked.
        # This catches added/deleted files, restored mtimes and changed tools.
        make_lines.extend(
            [
                str(stamp) + ": " + str(snapshot_path) + " " + dependency,
                "\t@"
                + shlex.quote(sys.executable)
                + " "
                + shlex.quote(str(Path(__file__)))
                + " execute "
                + shlex.quote(str(snapshot_path)),
            ]
        )
        by_stage[entry["stage"]].append(str(stamp))
    for stage, stamps in by_stage.items():
        make_lines.append(stage + ": " + " ".join(stamps))
        if not stamps:
            make_lines.append(
                "\t@echo 'ERROR: no backend configured for " + stage + "' >&2; exit 2"
            )
    make_lines.append("workflow: " + " ".join(config["workflow"]["stages"]))
    make_lines.append("sim-run: sim")
    sim_entries = [entry for entry in resolved if entry["stage"] == "sim"]
    if len(sim_entries) == 1:
        sim_input = GENERATED / "flows" / sim_entries[0]["id"] / "inputs.json"
        make_lines.append(
            "\t@"
            + shlex.quote(sys.executable)
            + " "
            + shlex.quote(str(Path(__file__)))
            + " execute-run "
            + shlex.quote(str(sim_input))
        )
    else:
        make_lines.append(
            "\t@echo 'ERROR: sim-run requires exactly one simulation technology/backend' >&2; exit 2"
        )
    atomic_write(GENERATED / "build.mk", "\n".join(make_lines) + "\n")
    write_json(
        GENERATED / "manifest.json",
        {
            "configuration": config,
            "configuration_digest": config_digest(config),
            "bender": provenance,
            "packages": package_state,
            "flows": {key: value["input_digest"] for key, value in snapshots.items()},
        },
    )
    return resolved


def preflight(config, snapshot):
    for name in config["environment"]["required_commands"]:
        if shutil.which(name) is None:
            raise ConfigError("Required command not found: " + name)
    for name in config["environment"]["required_variables"]:
        if not os.environ.get(name):
            raise ConfigError("Required environment variable is unset: " + name)
    for name, identity in snapshot["tools"].items():
        if not identity["available"]:
            raise ConfigError("Required tool not found: " + name)
        executable = Path(identity["path"])
        if (
            not executable.is_file()
            or sha256(executable) != identity["executable_sha256"]
        ):
            raise ConfigError("Tool changed after preparation: " + name)
        pin = config["environment"]["tool_versions"].get(name)
        if pin and pin not in identity["version"]:
            raise ConfigError("Tool version mismatch: " + name + " requires " + pin)
    entry = snapshot["entry"]
    expected_version = entry["settings"].get("version")
    actual = snapshot["tools"][entry["settings"]["_backend"]["tool"]]["version"]
    if expected_version and expected_version not in actual:
        raise ConfigError(
            "EDA version mismatch: expected " + expected_version + ", got " + actual
        )
    for path, checksum in {**snapshot["files"], **snapshot["exports"]}.items():
        if checksum is None:
            raise ConfigError("Required input is missing: " + path)
        if not Path(path).is_file() or sha256(Path(path)) != checksum:
            raise ConfigError("Input changed after preparation; rerun make: " + path)
    technology = config["technology"][entry["technology"]]
    assets = {asset["path"]: asset for asset in technology.get("assets", {}).values()}
    for path, asset in assets.items():
        if asset.get("sha256") and sha256(Path(path)) != asset["sha256"]:
            raise ConfigError("Technology asset checksum mismatch: " + path)
    if config["build"]["reproducible"]:
        if not expected_version:
            raise ConfigError("Reproducible builds require flow backend version pins")
        for name in snapshot["tools"]:
            if (
                name != entry["settings"]["_backend"]["tool"]
                and name not in config["environment"]["tool_versions"]
            ):
                raise ConfigError(
                    "Reproducible builds require environment.tool_versions." + name
                )
        if entry["stage"] == "sim" and not config["environment"]["packages"].get(
            "spdlog"
        ):
            raise ConfigError(
                "Reproducible simulation requires environment.packages.spdlog"
            )
        for path in snapshot["files"]:
            if not Path(path).is_relative_to(ROOT) and path not in assets:
                # External IP sources are pinned by Bender, technology assets by checksums.
                if not any(
                    Path(path).is_relative_to(Path(package["path"]))
                    for package in snapshot["packages"].values()
                    if package["path"] != str(ROOT)
                ):
                    raise ConfigError("Unpinned external asset: " + path)
        for path, asset in assets.items():
            if not asset.get("sha256"):
                raise ConfigError("Reproducible builds require asset SHA256: " + path)


def stream_command(argv, cwd, environment, log):
    log.write("$ " + shlex.join(argv) + "\n")
    log.flush()
    child = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        errors="replace",
        start_new_session=True,
    )
    try:
        for line in child.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
        return child.wait()
    except BaseException:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait()
        raise


def execute(snapshot_path, run=False):
    config = load_config(ROOT / "Project.toml", ROOT)
    snapshot = json.loads(snapshot_path.read_text())
    entry = snapshot["entry"]
    if entry not in entries(config):
        raise ConfigError("Stale or unrecognized stage descriptor; rerun make")
    expected_input = GENERATED / "flows" / entry["id"] / "inputs.json"
    if snapshot_path.resolve() != expected_input.resolve():
        raise ConfigError("Stage inputs must come from the generated flow directory")
    directory = stage_path(entry) / "run" if run else stage_path(entry)
    if not directory.resolve().is_relative_to((ROOT / "build").resolve()):
        raise ConfigError("Stage output directory resolves outside build/")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = directory / ".done"
    if stamp.exists():
        stamp.unlink()
    for name in ("work", "reports", "logs", "results"):
        if (directory / name).is_dir():
            shutil.rmtree(directory / name)
        (directory / name).mkdir(exist_ok=True)
    environment = dict(
        os.environ,
        PROJECT_ROOT=str(ROOT),
        RTL_TOP=config["architecture"]["top"],
        BUILD_JOBS=str(config["build"]["jobs"]),
        BENDER_SCRIPT=str(
            snapshot_path.parent
            / ("sources.tcl" if entry["stage"] in ("formal", "synth") else "sources.f")
        ),
        RTL_FILELIST=str(snapshot_path.parent / "sources.f"),
        STAGE_CONFIG=str(snapshot_path.parent / "backend.tcl"),
        CONSTRAINTS_SDC=str(GENERATED / "constraints.sdc"),
        STAGE_WORK_DIR=str(directory / "work"),
        STAGE_REPORT_DIR=str(directory / "reports"),
        STAGE_RESULT_DIR=str(directory / "results"),
        DEPENDENCY_RESULTS=str(stage_path(provider_for(config, entry)) / "results")
        if provider_for(config, entry)
        else "",
    )
    started = time.time()
    status = 1
    error = None
    result_commands = []
    artifacts = {}
    print(
        "["
        + entry["stage"].upper()
        + "::"
        + entry["technology"]
        + "::"
        + entry["tool"]
        + "] "
        + ("Running program" if run else "Executing stage"),
        flush=True,
    )
    with (directory / "logs/run.log").open("w") as log:
        try:
            if snapshot["configuration_digest"] != config_digest(config):
                raise ConfigError("Configuration changed after preparation; rerun make")
            preflight(config, snapshot)
            if run:
                argv = invoke(entry, "run", config, entry, stage_path(entry))
                if not argv:
                    raise ConfigError(
                        "This backend has no simulation run implementation"
                    )
                result_commands = [argv]
                snapshot = dict(
                    snapshot,
                    program={"path": argv[-1], "sha256": sha256(Path(argv[-1]))},
                    simulation_arguments=argv[1:],
                )
            else:
                result_commands = commands(
                    config,
                    entry,
                    ROOT,
                    directory,
                    snapshot_path.parent,
                    snapshot["input_digest"],
                )
            status = 0
            for argv in result_commands:
                status = stream_command(argv, directory / "work", environment, log)
                if status:
                    break
            if status == 0 and not run:
                invoke(entry, "collect", config, entry, directory, snapshot)
            summary = directory / "reports/summary.rpt"
            log.flush()
            if entry["stage"] in ("lint", "sim") and not summary.exists() or status:
                shutil.copyfile(directory / "logs/run.log", summary)
            if status == 0:
                # Never certify a run whose inputs were modified while EDA ran.
                preflight(config, snapshot)
                expected = [summary] if run else artifact_paths(config, entry)
                for path in expected:
                    if not path.is_file() or not path.stat().st_size:
                        raise ConfigError(
                            "Tool did not create required artifact: " + str(path)
                        )
                artifacts = {str(path): sha256(path) for path in expected}
        except (ConfigError, OSError, ValueError, KeyboardInterrupt) as exception:
            status = 130 if isinstance(exception, KeyboardInterrupt) else 1
            error = str(exception)
            print("ERROR: " + error, file=sys.stderr)
            log.write("ERROR: " + error + "\n")
        finally:
            log.flush()
            if status != 0:
                shutil.copyfile(
                    directory / "logs/run.log", directory / "reports/summary.rpt"
                )
            write_json(
                directory / "run.json",
                {
                    "schema_version": 2,
                    "status": "passed" if status == 0 else "failed",
                    "exit_code": status,
                    "started_epoch": started,
                    "finished_epoch": time.time(),
                    "commands": result_commands,
                    "inputs": snapshot,
                    "artifacts": artifacts,
                    "error": error,
                },
            )
            if status == 0 and not run:
                atomic_write(stamp, snapshot["input_digest"] + "\n")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "config",
            "deps-update",
            "lint",
            "synth",
            "formal",
            "sim",
            "sim-build",
            "sim-run",
            "workflow",
            "execute",
            "execute-run",
        ),
    )
    parser.add_argument("input", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        if args.action.startswith("execute"):
            return execute(args.input, args.action == "execute-run")
        (ROOT / "build").mkdir(exist_ok=True)
        with (ROOT / "build/.project.lock").open("a") as mutex:
            fcntl.flock(mutex, fcntl.LOCK_EX)
            config = load_config(ROOT / "Project.toml", ROOT)
            # Generated HDL must exist before Bender resolves/globs the package.
            for name, content in render_outputs(
                config, ROOT / "Project.toml", ROOT, GENERATED
            ).items():
                atomic_write(GENERATED / name, content)
            prepare(config, update=args.action == "deps-update")
            if args.action in ("config", "deps-update"):
                print("[CONFIG] Bender inputs and project configuration synchronized")
                return 0
            goals = (
                config["workflow"]["stages"]
                if args.action == "workflow"
                else ["sim" if args.action == "sim-build" else args.action]
            )
            if not goals:
                print("[WORKFLOW] No stages configured")
            for goal in goals:
                status = subprocess.call(
                    [
                        os.environ.get("PROJECT_MAKE", "make"),
                        "--no-print-directory",
                        "--keep-going",
                        "-f",
                        str(GENERATED / "build.mk"),
                        "-j",
                        str(config["build"]["jobs"]),
                        goal,
                    ],
                    cwd=ROOT,
                )
                if status:
                    return status
            return 0
    except (ConfigError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
