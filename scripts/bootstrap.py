"""Resolve dependencies before loading dicflow; user workflows are optional."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def settings_for(root):
    configuration = root / "Project.toml"
    if not configuration.is_file():
        raise RuntimeError("Project.toml is required for this workflow; run make init")
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
    if not isinstance(settings, dict) or set(settings) - {"version"}:
        raise RuntimeError(
            "[bender] may only pin version; dependencies belong to Bender.yml "
            "and project sources to [design]"
        )
    if "version" in settings and (
        not isinstance(settings["version"], str) or not settings["version"]
    ):
        raise RuntimeError("bender.version must be a version string")
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
    if not manifest.is_file():
        raise RuntimeError("Dependencies must be declared in the repository Bender.yml")
    settings = {} if updating else settings_for(root)
    if (
        settings.get("version")
        and bender(root, "--version") != "bender " + settings["version"]
    ):
        raise RuntimeError("Bender version does not match the configured version")
    if (root / "Bender.local").exists():
        raise RuntimeError("Bender.local overrides are not allowed in locked workflows")
    lock = root / "Bender.lock"
    (root / "build").mkdir(exist_ok=True)
    with (root / "build/.project.lock").open("a") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        previous = lock.read_bytes() if lock.exists() else None
        previous_manifest = manifest.read_bytes() if manifest.exists() else None
        try:
            if not updating and previous is None:
                raise RuntimeError("Bender.lock is missing; run make deps-update")
            if updating:
                bender(root, "update", "--fetch")
            if json.loads(bender(root, "config")).get("overrides"):
                raise RuntimeError("Bender overrides bypass the dependency declaration")
            locked = lock.read_bytes()
            bender(root, "checkout")
            if lock.read_bytes() != locked:
                raise RuntimeError("Ordinary checkout changed Bender.lock")
            if manifest.read_bytes() != previous_manifest:
                raise RuntimeError(
                    "Bender.yml changed during dependency resolution; rerun make"
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
