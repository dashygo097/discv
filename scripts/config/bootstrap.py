"""Stable project entry: locked Bender resolution and framework dispatch.

This file also supplies the native Bender adapter used by the framework.
Starter projects retain this bootstrap; tool policy executes from the locked
framework package. The bootstrap contract is versioned independently.
"""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

BOOTSTRAP_API = 1


class ConfigError(Exception):
    pass


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name, dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


LOCK_HEADER = "# Project dependency declaration SHA256: "


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def command(root, *arguments):
    environment = dict(os.environ)
    # A caller's BENDER_DIR must never redirect the golden project.
    for key in list(environment):
        if key.startswith("BENDER_"):
            environment.pop(key)
    result = subprocess.run(
        ["bender", "--no-progress", "-d", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    if result.returncode:
        raise ConfigError(
            "bender " + " ".join(arguments) + ":\n" + result.stderr.strip()
        )
    return result.stdout


def path(root, value):
    if not isinstance(value, str):
        raise ConfigError("Bender paths must be strings")
    return str(root / value) if not Path(value).is_absolute() else value


def source(root, value):
    if isinstance(value, str):
        return path(root, value)
    if not isinstance(value, dict):
        raise ConfigError("invalid Bender source group")
    result = dict(value)
    if "files" in result:
        result["files"] = [source(root, item) for item in result["files"]]
    for key in ("include_dirs", "external_flists"):
        if key in result:
            result[key] = [
                dict(item, dir=path(root, item["dir"]))
                if isinstance(item, dict)
                else path(root, item)
                for item in result[key]
            ]
    for key in ("sv", "v", "vhd"):
        if key in result:
            result[key] = path(root, result[key])
    return result


def manifest(config, root, frozen=True, generated_sources=()):
    settings = config["bender"]
    # Bender resolves project paths relative to its manifest. Keeping native
    # declarations relative also makes versioned library manifests relocatable.
    return {
        "package": {"name": settings["name"]},
        "frozen": frozen,
        "dependencies": settings.get("dependencies", {}),
        "export_include_dirs": settings.get("export_include_dirs", []),
        "sources": [*generated_sources, *settings["sources"]],
    }


def write_manifest(config, root, frozen=True, generated_sources=()):
    content = "# Generated from Project.toml; do not edit.\n"
    # JSON is a YAML subset, eliminating a second serializer/dependency.
    content += (
        json.dumps(manifest(config, root, frozen, generated_sources), indent=2) + "\n"
    )
    atomic_write(root / "Bender.yml", content)


def resolve(config, root, update=False, generated_sources=()):
    actual = subprocess.check_output(
        ["bender", "--version"], universal_newlines=True
    ).strip()
    expected = "bender " + config["bender"]["version"]
    if actual != expected:
        raise ConfigError(
            "Bender version mismatch: expected " + expected + ", got " + actual
        )
    declaration = digest(
        {
            "dependencies": config["bender"].get("dependencies", {}),
            "bender_version": config["bender"]["version"],
        }
    )
    lock = root / "Bender.lock"
    header = LOCK_HEADER + declaration + "\n"
    if (root / "Bender.local").exists():
        raise ConfigError(
            "Use bender.dependencies.<name>.path in Project.toml instead of Bender.local"
        )
    if not lock.exists() and not config["bender"].get("dependencies"):
        update = True
    if update:
        previous = lock.read_bytes() if lock.exists() else None
        try:
            write_manifest(
                config, root, frozen=False, generated_sources=generated_sources
            )
            command(root, "update")
            native_lock = lock.read_text()
            native_lock = (
                "\n".join(
                    line
                    for line in native_lock.splitlines()
                    if not line.startswith(LOCK_HEADER)
                )
                + "\n"
            )
            atomic_write(lock, header + native_lock)
        except Exception:
            if previous is None:
                if lock.exists():
                    lock.unlink()
            else:
                atomic_write(lock, previous.decode())
            raise
        finally:
            write_manifest(
                config, root, frozen=True, generated_sources=generated_sources
            )
    else:
        if not lock.exists() or not lock.read_text().startswith(header):
            raise ConfigError(
                "Package declarations changed or Bender.lock is missing; run make deps-update"
            )
        write_manifest(config, root, generated_sources=generated_sources)
    before = lock.read_bytes()
    effective = json.loads(command(root, "config"))
    if effective.get("overrides"):
        raise ConfigError(
            "Bender configuration overrides bypass Project.toml; declare path dependencies in the golden configuration"
        )
    command(root, "checkout")
    if lock.read_bytes() != before:
        atomic_write(lock, before.decode())
        raise ConfigError("Ordinary builds must not modify Bender.lock")
    executable = Path(shutil.which("bender"))
    return {
        "version": actual,
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256(before).hexdigest(),
        "effective_config": effective,
    }


def sources(root, targets):
    args = [part for target in targets for part in ("-t", target)]
    groups = json.loads(command(root, "sources", "-f", *args))
    if not groups or not any(group["files"] for group in groups):
        raise ConfigError(
            "Bender resolved no sources for targets: " + ", ".join(targets)
        )
    return groups


def export(root, targets, format_name):
    args = [part for target in targets for part in ("-t", target)]
    # Never let different export formats introduce different implicit target sets.
    content = command(root, "script", "--no-default-target", *args, format_name)
    if format_name == "verilator":
        # Bender 0.32 emits one argument per line without quoting whitespace.
        # Preserve its arguments/order while encoding them for Verilator's -f
        # parser; source discovery and target selection remain native Bender.
        lines = []
        for line in content.splitlines():
            if line and not line.lstrip().startswith(("//", "#")):
                line = '"' + line.replace("\\", "\\\\").replace('"', '\\"') + '"'
            lines.append(line)
        content = "\n".join(lines) + "\n"
    return content


def packages(root, reproducible):
    names = command(root, "packages", "-f").split()
    result = {}
    for name in names:
        directory = Path(command(root, "path", name).strip())
        if not directory.is_dir():
            raise ConfigError("Missing package checkout: " + name)
        git = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        state = {"path": str(directory)}
        # Path packages nested in a parent repo are not separate Git checkouts.
        if git.returncode == 0:
            state["git_root"] = git.stdout.strip()
            state["revision"] = subprocess.check_output(
                ["git", "-C", str(directory), "rev-parse", "HEAD"],
                universal_newlines=True,
            ).strip()
            state["dirty"] = bool(
                subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(directory),
                        "status",
                        "--porcelain",
                        "--untracked-files=all",
                    ],
                    universal_newlines=True,
                ).strip()
            )
        if reproducible and (state.get("dirty") or "revision" not in state):
            raise ConfigError(
                "Reproducible build requires a clean revision-pinned package: " + name
            )
        result[name] = state
    return result


def framework_package(config):
    if "framework" not in config:
        return None
    settings = config["framework"]
    if not isinstance(settings, dict) or set(settings) != {"package"}:
        raise ConfigError("framework: expected only package = <Bender dependency name>")
    name = settings["package"]
    if not isinstance(name, str) or not name.isidentifier():
        raise ConfigError("framework.package: expected a Bender dependency name")
    if name not in config.get("bender", {}).get("dependencies", {}):
        raise ConfigError(
            f"framework.package: {name} must be declared in bender.dependencies"
        )
    return name


def main():
    arguments = sys.argv[1:]
    if not arguments:
        raise ConfigError("Use make <stage> or make deps-update")
    root = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()
    with (root / "Project.toml").open("rb") as stream:
        config = tomllib.load(stream)
    package = framework_package(config)
    environment = dict(
        os.environ,
        PROJECT_ROOT=str(root),
        PROJECT_BOOTSTRAP_API=str(BOOTSTRAP_API),
        PYTHONDONTWRITEBYTECODE="1",
    )
    for name in (
        "PROJECT_FRAMEWORK_PACKAGE",
        "PROJECT_FRAMEWORK_ROOT",
        "PROJECT_BOOTSTRAP_UPDATED_LOCK",
    ):
        environment.pop(name, None)
    engine = Path(__file__).with_name("flow.py")
    if package:
        (root / "build").mkdir(exist_ok=True)
        with (root / "build/.project.lock").open("a") as mutex:
            fcntl.flock(mutex, fcntl.LOCK_EX)
            # HDL generators have not run yet. Resolve the package graph using
            # an empty root fileset; the engine projects the complete manifest.
            declaration = {
                "bender": {**config["bender"], "sources": [], "export_include_dirs": []}
            }
            updating = arguments[0] == "deps-update"
            lock = root / "Bender.lock"
            previous = lock.read_text() if lock.exists() else None
            try:
                provenance = resolve(declaration, root, update=updating)
                directory = Path(command(root, "path", package).strip()).resolve()
                engine = directory / "scripts/config/flow.py"
                if not engine.is_file():
                    raise ConfigError(f"Framework entry does not exist: {engine}")
            except BaseException:
                if updating:
                    if previous is None:
                        lock.unlink(missing_ok=True)
                    else:
                        atomic_write(lock, previous)
                raise
            environment.update(
                PROJECT_FRAMEWORK_PACKAGE=package, PROJECT_FRAMEWORK_ROOT=str(directory)
            )
            if updating:
                environment["PROJECT_BOOTSTRAP_UPDATED_LOCK"] = provenance[
                    "lock_sha256"
                ]
    if not engine.is_file():
        raise ConfigError(f"Framework entry does not exist: {engine}")
    os.execve(sys.executable, [sys.executable, str(engine), *arguments], environment)


if __name__ == "__main__":
    try:
        main()
    except (ConfigError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        raise SystemExit(1)
