"""Resolve dependencies before loading dicflow; user workflows are optional."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HEADER = "# Project dependency declaration SHA256: "
GENERATED = b"# Generated from Project.toml;"


def remove_tree(path):
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def clean(root, *, entire):
    # Cleanup must work offline, without config, dependencies or a usable venv.
    build = root / "build"
    if build.is_symlink():
        raise RuntimeError("Refusing to clean a build/ symlink")
    build.mkdir(exist_ok=True)
    with (build / ".project.lock").open("a") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        if entire:
            remove_tree(build)
        else:
            for directory in build.iterdir():
                if directory.is_dir() and (directory / ".flow-stage").is_file():
                    remove_tree(directory)
            remove_tree(build / "generated")
        manifest = root / "Bender.yml"
        if manifest.is_file() and manifest.read_bytes().startswith(GENERATED):
            manifest.unlink()
        if entire:
            try:
                (root / "Project.toml").unlink()
            except FileNotFoundError:
                pass
    if entire:
        print(
            "[DISTCLEAN] build/ and Project.toml removed; native package metadata preserved"
        )
    else:
        print(
            "[CLEAN] Flow outputs removed; configuration, environment and lock preserved"
        )


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


def settings_for(root, updating, native):
    # Native Bender owns package dependencies; updating them needs no user config
    # or TOML parser. Project mode projects its dependency metadata from TOML.
    if native and updating:
        return {}
    configuration = root / "Project.toml"
    if not configuration.is_file():
        if not updating:
            hint = (
                "run make init"
                if (root / ".project.template.toml").is_file()
                else "create a local Project.toml to configure workflows"
            )
            raise RuntimeError(f"Project.toml is required for this workflow; {hint}")
        configuration = root / ".project.template.toml"
        if not configuration.is_file():
            raise RuntimeError(
                "Dependency updates require a native Bender.yml or dependency "
                "declarations in Project.toml / .project.template.toml; "
                "Bender.lock records resolved versions, not update requirements"
            )
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as error:
            raise RuntimeError(
                "Bootstrap requires Python 3.11+ or tomli; select it with BOOTSTRAP_PYTHON"
            ) from error
    with configuration.open("rb") as stream:
        project = tomllib.load(stream)
    if "framework" in project:
        raise RuntimeError("Remove [framework]; declare dicflow as a Bender dependency")
    settings = project.get("bender", {})
    if not isinstance(settings, dict):
        raise RuntimeError("[bender] must be a table")
    if native:
        if set(settings) - {"version"}:
            raise RuntimeError(
                "Native packages keep HDL metadata in Bender.yml; "
                "[bender] may only pin version"
            )
    else:
        if not isinstance(settings.get("name"), str) or not settings["name"]:
            raise RuntimeError(f"{configuration.name}: bender.name is required")
        if not isinstance(settings.get("sources"), list):
            raise RuntimeError("Native package flows require a native Bender.yml")
        if (
            not isinstance(settings.get("dependencies"), dict)
            or "dicflow" not in settings["dependencies"]
        ):
            raise RuntimeError(
                f"{configuration.name}: declare bender.dependencies.dicflow"
            )
    if (not native or "version" in settings) and (
        not isinstance(settings.get("version"), str) or not settings["version"]
    ):
        raise RuntimeError(
            f"{configuration.name}: bender.version must be a version string"
        )
    return settings


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    root = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()
    if action in {"clean", "distclean"}:
        clean(root, entire=action == "distclean")
        return
    if action == "help":
        initialize = "init, " if (root / ".project.template.toml").is_file() else ""
        print(
            f"Use make {initialize}deps-update, env, <stage>, workflow, clean or distclean."
        )
        print(
            "deps-update needs no Project.toml; workflows use your local Project.toml."
        )
        return
    updating = action == "deps-update"
    manifest = root / "Bender.yml"
    native = manifest.is_file() and not manifest.read_bytes().startswith(GENERATED)
    settings = settings_for(root, updating, native)
    if (
        settings.get("version")
        and bender(root, "--version") != "bender " + settings["version"]
    ):
        raise RuntimeError("Bender version does not match the configured version")
    if (root / "Bender.local").exists():
        raise RuntimeError("Bender.local overrides are not allowed in locked workflows")
    header = ""
    if not native:
        declaration = {
            "dependencies": settings["dependencies"],
            "bender_version": settings["version"],
        }
        signature = hashlib.sha256(
            json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        header = HEADER + signature + "\n"
    lock = root / "Bender.lock"
    (root / "build").mkdir(exist_ok=True)
    with (root / "build/.project.lock").open("a") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        previous = lock.read_bytes() if lock.exists() else None
        previous_manifest = manifest.read_bytes() if manifest.exists() else None
        try:
            if not updating and (
                previous is None
                or (not native and not previous.startswith(header.encode()))
            ):
                raise RuntimeError(
                    "Dependency declaration changed or Bender.lock is missing; run make deps-update"
                )
            if not native:
                manifest.write_text(
                    GENERATED.decode()
                    + " do not edit.\n"
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
            if json.loads(bender(root, "config")).get("overrides"):
                raise RuntimeError("Bender overrides bypass the dependency declaration")
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
            locked = lock.read_bytes()
            bender(root, "checkout")
            if lock.read_bytes() != locked:
                raise RuntimeError("Ordinary checkout changed Bender.lock")
            if native and manifest.read_bytes() != previous_manifest:
                raise RuntimeError(
                    "Native Bender.yml changed during dependency resolution; rerun make"
                )
            if not updating:
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
    if updating:
        print(
            "[DEPS] Bender dependencies updated; Bender.lock records resolved revisions"
        )
        return
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
