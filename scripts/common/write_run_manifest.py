#!/usr/bin/env python3
"""Write a machine-readable stage execution manifest."""

import argparse
import json
import os
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--started", type=int, required=True)
    parser.add_argument("--finished", type=int, required=True)
    parser.add_argument("--configuration-digest", required=True)
    parser.add_argument("--project-manifest", type=Path, required=True)
    parser.add_argument("--stage-build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def relative_artifact(stage_build_dir, path):
    if not path.exists():
        return None
    if path.is_dir() and not any(path.iterdir()):
        return None
    return path.relative_to(stage_build_dir).as_posix()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        os.replace(temporary_name, str(path))
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def main():
    args = parse_args()
    stage_build_dir = args.stage_build_dir.resolve()
    project_manifest = json.loads(args.project_manifest.read_text(encoding="utf-8"))
    manifest_digest = project_manifest.get("configuration_digest")
    if manifest_digest != args.configuration_digest:
        raise SystemExit(
            "ERROR: project manifest and stage environment have different "
            "configuration digests"
        )

    tool_version_path = stage_build_dir / "work" / "tool-version.txt"
    tool_version = None
    if tool_version_path.is_file():
        tool_version = tool_version_path.read_text(encoding="utf-8").strip() or None

    artifacts = {}
    artifact_paths = {
        "log": stage_build_dir / "logs" / "run.log",
        "summary": stage_build_dir / "reports" / "summary.rpt",
        "reports": stage_build_dir / "reports",
        "results": stage_build_dir / "results",
    }
    for name, path in sorted(artifact_paths.items()):
        relative_path = relative_artifact(stage_build_dir, path)
        if relative_path is not None:
            artifacts[name] = relative_path

    run_manifest = {
        "artifacts": artifacts,
        "configuration_digest": args.configuration_digest,
        "duration_seconds": max(0, args.finished - args.started),
        "exit_code": args.exit_code,
        "finished_epoch": args.finished,
        "rtl_top": project_manifest["rtl"]["top"],
        "schema_version": 1,
        "stage": args.stage,
        "started_epoch": args.started,
        "status": "passed" if args.exit_code == 0 else "failed",
        "tool": args.tool,
        "tool_version": tool_version,
    }
    atomic_write(
        args.output,
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
