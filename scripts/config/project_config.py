#!/usr/bin/env python3
"""Validate Project.toml and generate build-system projections."""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.stderr.write(
            "ERROR: TOML parser unavailable; install scripts/config/requirements.txt\n"
        )
        raise SystemExit(2)


GENERATOR_VERSION = "0.1.0"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(Exception):
    pass


def reject_unknown(table, allowed, location):
    unknown = sorted(set(table) - set(allowed))
    if unknown:
        raise ConfigError(
            "{}: unknown key(s): {}".format(location, ", ".join(unknown))
        )


def require_string(table, key, location):
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError("{}.{}: expected a non-empty string".format(location, key))
    return value


def string_list(value, location):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError("{}: expected an array of strings".format(location))
    return value


def require_table(raw, key):
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError("{}: expected a table".format(key))
    return value


def require_bool(table, key, location):
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError("{}.{}: expected a boolean".format(location, key))
    return value


def load_config(config_path, project_root):
    with config_path.open("rb") as stream:
        raw = tomllib.load(stream)

    reject_unknown(
        raw,
        {"schema_version", "project", "rtl", "build", "environment", "flow", "workflow"},
        "<root>",
    )
    if raw.get("schema_version") != 1:
        raise ConfigError("schema_version: expected integer 1")

    project = require_table(raw, "project")
    reject_unknown(project, {"name"}, "project")
    name = require_string(project, "name", "project")

    rtl = require_table(raw, "rtl")
    reject_unknown(rtl, {"top", "sources", "include_dirs", "defines"}, "rtl")
    top = require_string(rtl, "top", "rtl")
    if not IDENTIFIER.match(top):
        raise ConfigError("rtl.top: invalid SystemVerilog identifier")
    source_names = string_list(rtl.get("sources", []), "rtl.sources")
    include_names = string_list(rtl.get("include_dirs", []), "rtl.include_dirs")
    defines = rtl.get("defines", {})
    if not isinstance(defines, dict):
        raise ConfigError("rtl.defines: expected a table")

    normalized_defines = {}
    for key in sorted(defines):
        if not IDENTIFIER.match(key):
            raise ConfigError("rtl.defines.{}: invalid identifier".format(key))
        value = defines[key]
        if not isinstance(value, (str, int, bool)):
            raise ConfigError(
                "rtl.defines.{}: expected string, integer, or boolean".format(key)
            )
        normalized_defines[key] = value

    sources = [(project_root / item).resolve() for item in source_names]
    include_dirs = [(project_root / item).resolve() for item in include_names]
    for path in sources:
        if not path.is_file():
            raise ConfigError("RTL source does not exist: {}".format(path))
    for path in include_dirs:
        if not path.is_dir():
            raise ConfigError("RTL include directory does not exist: {}".format(path))
    headers = sorted(
        str(path.resolve())
        for directory in include_dirs
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".h", ".vh", ".svh"}
    )

    build = require_table(raw, "build")
    reject_unknown(build, {"jobs"}, "build")
    jobs = build.get("jobs")
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ConfigError("build.jobs: expected a positive integer")

    environment = require_table(raw, "environment")
    reject_unknown(
        environment,
        {"python", "required_commands", "required_variables"},
        "environment",
    )
    python = require_string(environment, "python", "environment")
    required_commands = string_list(
        environment.get("required_commands", []), "environment.required_commands"
    )
    required_variables = string_list(
        environment.get("required_variables", []), "environment.required_variables"
    )
    for variable in required_variables:
        if not IDENTIFIER.match(variable):
            raise ConfigError(
                "environment.required_variables: invalid variable name: {}".format(variable)
            )

    flow = require_table(raw, "flow")
    reject_unknown(flow, {"lint"}, "flow")
    lint = flow.get("lint")
    if not isinstance(lint, dict):
        raise ConfigError("flow.lint: expected a table")
    reject_unknown(lint, {"enabled", "tool", "options"}, "flow.lint")
    lint_enabled = require_bool(lint, "enabled", "flow.lint")
    lint_tool = lint.get("tool")
    if not isinstance(lint_tool, str):
        raise ConfigError("flow.lint.tool: expected a string")
    lint_options = string_list(lint.get("options", []), "flow.lint.options")
    if lint_enabled and not lint_tool:
        raise ConfigError("flow.lint.tool: required when lint is enabled")
    if lint_enabled and lint_tool != "verilator":
        raise ConfigError("flow.lint.tool: supported value is 'verilator'")

    workflow = require_table(raw, "workflow")
    reject_unknown(workflow, {"stages"}, "workflow")
    stages = string_list(workflow.get("stages", []), "workflow.stages")
    unsupported = sorted(set(stages) - {"lint"})
    if unsupported:
        raise ConfigError("workflow.stages: unsupported stage(s): {}".format(", ".join(unsupported)))
    if "lint" in stages and not lint_enabled:
        raise ConfigError("workflow.stages: lint is listed but flow.lint.enabled is false")
    if len(stages) != len(set(stages)):
        raise ConfigError("workflow.stages: duplicate stages are not allowed")

    return {
        "schema_version": 1,
        "project": {"name": name},
        "rtl": {
            "top": top,
            "sources": [str(path) for path in sources],
            "include_dirs": [str(path) for path in include_dirs],
            "headers": headers,
            "defines": normalized_defines,
        },
        "build": {"jobs": jobs},
        "environment": {
            "python": python,
            "required_commands": required_commands,
            "required_variables": required_variables,
        },
        "flow": {
            "lint": {
                "enabled": lint_enabled,
                "tool": lint_tool,
                "options": lint_options,
            }
        },
        "workflow": {"stages": stages},
    }


def config_digest(config):
    encoded = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def header(comment, digest):
    return (
        "{0} Generated by project_config.py; do not edit.\n"
        "{0} Configuration digest: {1}\n".format(comment, digest)
    )


def render_filelist(config, digest):
    lines = [header("#", digest).rstrip()]
    lines.extend("+incdir+{}".format(path) for path in config["rtl"]["include_dirs"])
    for name, value in sorted(config["rtl"]["defines"].items()):
        if isinstance(value, bool):
            if value:
                lines.append("+define+{}".format(name))
        else:
            lines.append("+define+{}={}".format(name, value))
    lines.extend(config["rtl"]["sources"])
    return "\n".join(lines) + "\n"


def make_escape(value):
    return value.replace("$", "$$").replace("#", "\\#")


def render_makefile(config, digest):
    return "".join(
        [
            header("#", digest),
            "PROJECT_NAME := {}\n".format(make_escape(config["project"]["name"])),
            "PROJECT_TOP := {}\n".format(make_escape(config["rtl"]["top"])),
            "BUILD_JOBS := {}\n".format(config["build"]["jobs"]),
            "LINT_ENABLED := {}\n".format("1" if config["flow"]["lint"]["enabled"] else "0"),
            "LINT_TOOL := {}\n".format(make_escape(config["flow"]["lint"]["tool"])),
            "WORKFLOW_STAGES := {}\n".format(" ".join(config["workflow"]["stages"])),
            "RTL_SOURCES := {}\n".format(" ".join(make_escape(path) for path in config["rtl"]["sources"])),
            "RTL_HEADERS := {}\n".format(" ".join(make_escape(path) for path in config["rtl"]["headers"])),
            "PROJECT_CONFIG_DIGEST := {}\n".format(digest),
        ]
    )


def shell_array(name, values):
    return "{}=({})\n".format(name, " ".join(shlex.quote(str(value)) for value in values))


def render_environment(config, digest):
    lint = config["flow"]["lint"]
    return "".join(
        [
            header("#", digest),
            "PROJECT_NAME={}\n".format(shlex.quote(config["project"]["name"])),
            "RTL_TOP={}\n".format(shlex.quote(config["rtl"]["top"])),
            "BUILD_JOBS={}\n".format(config["build"]["jobs"]),
            "PROJECT_PYTHON={}\n".format(shlex.quote(config["environment"]["python"])),
            "LINT_ENABLED={}\n".format("1" if lint["enabled"] else "0"),
            "LINT_TOOL={}\n".format(shlex.quote(lint["tool"])),
            "LINT_OPTION_COUNT={}\n".format(len(lint["options"])),
            shell_array("LINT_OPTIONS", lint["options"]),
            shell_array("PROJECT_REQUIRED_COMMANDS", config["environment"]["required_commands"]),
            shell_array("PROJECT_REQUIRED_VARIABLES", config["environment"]["required_variables"]),
            "WORKFLOW_STAGE_COUNT={}\n".format(len(config["workflow"]["stages"])),
            shell_array("WORKFLOW_STAGES", config["workflow"]["stages"]),
        ]
    )


def render_outputs(config, config_path):
    digest = config_digest(config)
    manifest = {
        "configuration_digest": digest,
        "generator_version": GENERATOR_VERSION,
        "project_file": str(config_path.resolve()),
        "schema_version": config["schema_version"],
        "outputs": ["manifest.json", "project.env", "project.mk", "rtl.f"],
    }
    return {
        "rtl.f": render_filelist(config, digest),
        "project.mk": render_makefile(config, digest),
        "project.env": render_environment(config, digest),
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    }


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix="." + path.name, dir=str(path.parent))
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


def check_outputs(output_dir, outputs):
    stale = []
    for name, expected in sorted(outputs.items()):
        path = output_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(name)
    if stale:
        raise ConfigError("missing or stale generated file(s): {}".format(", ".join(stale)))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "generate", "check"))
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = args.config.resolve()
    project_root = args.project_root.resolve()
    try:
        config = load_config(config_path, project_root)
        if args.command == "validate":
            print("Configuration is valid: {}".format(config_path))
            return 0
        if args.output is None:
            raise ConfigError("--output is required for {}".format(args.command))
        output_dir = args.output.resolve()
        outputs = render_outputs(config, config_path)
        if args.command == "generate":
            for name, content in sorted(outputs.items()):
                atomic_write(output_dir / name, content)
            print("Generated configuration: {}".format(output_dir))
        else:
            check_outputs(output_dir, outputs)
            print("Generated configuration is current: {}".format(output_dir))
        return 0
    except (ConfigError, OSError, tomllib.TOMLDecodeError) as error:
        sys.stderr.write("ERROR: {}\n".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
