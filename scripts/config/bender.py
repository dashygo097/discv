"""Native Bender manifest projection, locked resolution and script exports."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from project_config import ConfigError, atomic_write

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
    dependencies = {}
    for name, spec in settings.get("dependencies", {}).items():
        spec = dict(spec) if isinstance(spec, dict) else spec
        if isinstance(spec, dict) and "path" in spec:
            spec["path"] = path(root, spec["path"])
        dependencies[name] = spec
    return {
        "package": {"name": settings["name"]},
        "frozen": frozen,
        "dependencies": dependencies,
        "export_include_dirs": [
            path(root, item) for item in settings.get("export_include_dirs", [])
        ],
        "sources": [
            source(root, item) for item in [*generated_sources, *settings["sources"]]
        ],
    }


def write_manifest(config, root, frozen=True, generated_sources=()):
    content = "# Generated from Project.toml; do not edit.\n"
    # JSON is a YAML subset, eliminating a second serializer/dependency.
    content += json.dumps(manifest(config, root, frozen, generated_sources), indent=2) + "\n"
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
            write_manifest(config, root, frozen=False, generated_sources=generated_sources)
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
            write_manifest(config, root, frozen=True, generated_sources=generated_sources)
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
    return command(root, "script", "--no-default-target", *args, format_name)


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
