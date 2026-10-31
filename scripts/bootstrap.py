"""Pre-download entry only; runtime policy and environment setup live in dicflow."""

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HEADER = "# Project dependency declaration SHA256: "


def bender(root, *arguments):
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("BENDER_")
    }
    result = subprocess.run(
        ["bender", "--no-progress", "-d", str(root), *arguments],
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    root = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()
    if action == "help":
        print(
            "Edit Project.toml; use make init, env, deps-update, <stage>, workflow, clean or distclean."
        )
        return
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as error:
            raise RuntimeError(
                "Bootstrap requires Python 3.11+ or tomli; select it with BOOTSTRAP_PYTHON"
            ) from error
    with (root / "Project.toml").open("rb") as stream:
        project = tomllib.load(stream)
    if "framework" in project:
        raise RuntimeError(
            "Remove [framework]; bender.dependencies.dicflow selects dicflow"
        )
    settings = project["bender"]
    native = "sources" not in settings
    manifest = root / "Bender.yml"
    if native:
        if set(settings) != {"version"}:
            raise RuntimeError(
                "Native packages keep HDL metadata in Bender.yml; [bender] only specifies version"
            )
        if not manifest.is_file() or manifest.read_bytes().startswith(
            b"# Generated from Project.toml;"
        ):
            raise RuntimeError("Native package flows require a native Bender.yml")
        declaration = {
            "native_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "bender_version": settings["version"],
        }
    else:
        if "dicflow" not in settings.get("dependencies", {}):
            raise RuntimeError("Project.toml must declare bender.dependencies.dicflow")
        declaration = {
            "dependencies": settings["dependencies"],
            "bender_version": settings["version"],
        }
    if bender(root, "--version") != "bender " + settings["version"]:
        raise RuntimeError("Bender version does not match Project.toml")
    if (root / "Bender.local").exists():
        raise RuntimeError("Bender.local overrides are not allowed in locked workflows")
    declaration = hashlib.sha256(
        json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    header = HEADER + declaration + "\n"
    updating = action == "deps-update"
    lock = root / "Bender.lock"
    (root / "build").mkdir(exist_ok=True)
    with (root / "build/.project.lock").open("a") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        previous = lock.read_bytes() if lock.exists() else None
        previous_manifest = manifest.read_bytes() if manifest.exists() else None
        if (
            not native
            and previous_manifest is not None
            and not previous_manifest.startswith(b"# Generated from Project.toml;")
        ):
            raise RuntimeError(
                "Refusing to overwrite a native Bender.yml with project configuration"
            )
        try:
            if not updating and (
                previous is None or not previous.startswith(header.encode())
            ):
                raise RuntimeError(
                    "Dependency declaration changed or Bender.lock is missing; run make deps-update"
                )
            if not native:
                manifest.write_text(
                    "# Generated from Project.toml; do not edit.\n"
                    + json.dumps(
                        {
                            "package": {"name": settings["name"]},
                            "frozen": not updating,
                            "dependencies": settings["dependencies"],
                            "sources": [],
                        },
                        indent=2,
                    )
                    + "\n"
                )
            if updating:
                bender(root, "update", "--fetch")
                native_lock = (
                    "\n".join(
                        line
                        for line in lock.read_text().splitlines()
                        if not line.startswith(HEADER)
                    )
                    + "\n"
                )
                lock.write_text(header + native_lock)
            if json.loads(bender(root, "config")).get("overrides"):
                raise RuntimeError("Bender overrides bypass Project.toml")
            locked = lock.read_bytes()
            bender(root, "checkout")
            if lock.read_bytes() != locked:
                raise RuntimeError("Ordinary checkout changed Bender.lock")
            if native and manifest.read_bytes() != previous_manifest:
                raise RuntimeError(
                    "Native Bender.yml changed during dependency resolution; rerun make"
                )
            directory = Path(bender(root, "path", "dicflow")).resolve()
            entry = directory / "scripts/config/entry.py"
            if not entry.is_file():
                raise RuntimeError(
                    "Locked dicflow lacks bootstrap API 2; run make deps-update"
                )
        except BaseException:
            if previous is None:
                lock.unlink(missing_ok=True)
            else:
                lock.write_bytes(previous)
            if not native:
                if previous_manifest is None:
                    manifest.unlink(missing_ok=True)
                else:
                    manifest.write_bytes(previous_manifest)
            raise
    environment = dict(
        os.environ,
        PROJECT_ROOT=str(root),
        PROJECT_FRAMEWORK_ROOT=str(directory),
        PROJECT_BOOTSTRAP_API="2",
        PROJECT_BOOTSTRAP_LOCK=hashlib.sha256(locked).hexdigest(),
        PYTHONDONTWRITEBYTECODE="1",
    )
    os.execve(sys.executable, [sys.executable, str(entry), *sys.argv[1:]], environment)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
