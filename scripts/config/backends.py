"""Backend contract. Tool policy lives beside the tool.

BACKEND declares tool/version_args, Bender format/source, commands, outputs,
input globs, technology_inputs, tracked_environment and environment templates.
generated_sources declares native Bender groups relative to build/generated;
these configuration packages precede handwritten RTL in the projected manifest.
summary="log" opts into using the execution log as the summary report.
inherit_targets=True uses the prerequisite's source targets (e.g. equivalence).

Optional hooks:
  configure(config, settings, root): validate/normalize backend-owned settings.
  generate(config, settings, root): shared generated files, relative to build/generated.
  prepare(config, entry, root, directory, source): per-entry generated files.
  tools(config, entry): extra tool identities as {name: [command, version_args...]}.
  preflight(config, entry, root): backend-specific execution requirements.
  collect(config, entry, directory, snapshot): publish native tool artifacts.
  run(config, entry, directory): {commands: [...], inputs: [file paths...]}.

Generation hooks return {relative_path: text}. Shared outputs must agree across
entries. Commands are argv arrays; arbitrary options remain backend-owned.
"""

import runpy
from pathlib import Path

from project_config import ConfigError, string_list


def load_backend(root, stage, name, settings):
    backend = settings.get("backend", name)
    if not isinstance(backend, str) or "/" in backend or ".." in backend:
        raise ConfigError("backend must name a backend description")
    definition = root / "scripts" / stage / (backend + "_backend.py")
    if not definition.is_file():
        raise ConfigError("Backend description does not exist: " + str(definition))
    description = dict(runpy.run_path(str(definition))["BACKEND"])
    for key in ("tool", "format"):
        if not isinstance(description.get(key), str) or not description[key]:
            raise ConfigError(f"{definition}: missing backend {key}")
    description.setdefault("version_args", ["--version"])
    string_list(description["version_args"], "backend version_args")
    description.setdefault("source", "sources.f")
    source = description["source"]
    if not isinstance(source, str) or not source or Path(source).name != source:
        raise ConfigError(f"{definition}: source must be a filename")
    resolved = {**description.pop("defaults", {}), **settings}
    for key in ("options", "targets"):
        resolved.setdefault(key, [])
        string_list(resolved[key], key)
    if "inputs" in resolved:
        string_list(resolved["inputs"], "inputs")
    if "version" in resolved and not isinstance(resolved["version"], str):
        raise ConfigError("version: expected a string")
    for key in ("commands", "outputs"):
        value = resolved.get(key, description.get(key))
        if key == "outputs":
            string_list(value, "backend outputs")
        elif not isinstance(value, list) or not value:
            raise ConfigError("backend commands: expected non-empty argv arrays")
        else:
            for argv in value:
                if not string_list(argv, "backend command"):
                    raise ConfigError("backend command: argv must not be empty")
    script = resolved.get("script")
    if script:
        resolved["script"] = str((root / script).resolve())
    elif description.get("script"):
        resolved["script"] = str(definition.parent / description["script"])
    description["definition"] = str(definition)
    resolved["_backend"] = description
    return resolved


def tcl_value(value):
    if isinstance(value, dict):
        return (
            "[dict create "
            + " ".join(
                tcl_value(key) + " " + tcl_value(item) for key, item in value.items()
            )
            + "]"
        )
    if isinstance(value, list):
        return "[list " + " ".join(tcl_value(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    # Quote data, never Tcl expressions. Backend settings may contain braces,
    # bus selectors, dollars or backslashes.
    escaped = str(value)
    for character, replacement in (
        ("\\", "\\\\"),
        ('"', '\\"'),
        ("$", "\\$"),
        ("[", "\\["),
        ("\n", "\\n"),
        ("\r", "\\r"),
    ):
        escaped = escaped.replace(character, replacement)
    return '"' + escaped + '"'


def configuration_tcl(config, entry):
    # Arbitrary backend/technology fields pass through without a Python schema.
    return (
        "set PROJECT "
        + tcl_value(
            {
                "architecture": config["architecture"],
                "build": config["build"],
                "flow": {
                    key: value
                    for key, value in entry["settings"].items()
                    if key != "_backend"
                },
                "technology": config["technology"][entry["technology"]],
            }
        )
        + "\n"
    )


def context(config, entry, root, stage_dir, inputs, input_digest):
    return {
        "root": str(root),
        "work": str(stage_dir / "work"),
        "results": str(stage_dir / "results"),
        "reports": str(stage_dir / "reports"),
        "model": str(stage_dir / "model" / input_digest),
        "inputs": str(inputs),
        "generated": str(root / "build/generated"),
        "top": config["architecture"]["top"],
        "jobs": str(config["build"]["jobs"]),
        "script": entry["settings"].get("script", ""),
        "input_digest": input_digest,
    }


def commands(config, entry, root, stage_dir, inputs, input_digest):
    values = context(config, entry, root, stage_dir, inputs, input_digest)
    definitions = entry["settings"].get(
        "commands", entry["settings"]["_backend"]["commands"]
    )
    result = []
    for argv in definitions:
        command = []
        for argument in argv:
            if argument == "{options}":
                command.extend(entry["settings"]["options"])
            else:
                command.append(argument.format_map(values))
        result.append(command)
    return result


def declared_outputs(config, entry, root, stage_dir, inputs, input_digest):
    values = context(config, entry, root, stage_dir, inputs, input_digest)
    patterns = entry["settings"].get(
        "outputs", entry["settings"]["_backend"]["outputs"]
    )
    return [Path(pattern.format_map(values)) for pattern in patterns]


def technology_inputs(technology, selectors):
    def leaves(value):
        if isinstance(value, dict):
            return [path for item in value.values() for path in leaves(item)]
        if isinstance(value, list):
            return [path for item in value for path in leaves(item)]
        return [value] if isinstance(value, str) else []

    result = []
    for selector in selectors:
        value = technology
        for key in selector.split("."):
            value = value.get(key, {}) if isinstance(value, dict) else {}
        result.extend(leaves(value))
    return result


def environment(config, entry, root, stage_dir, inputs, input_digest):
    values = context(config, entry, root, stage_dir, inputs, input_digest)
    return {
        name: value.format_map(values)
        for name, value in entry["settings"]["_backend"].get("environment", {}).items()
    }


def invoke(settings, hook, *arguments):
    function = runpy.run_path(settings["_backend"]["definition"]).get(hook)
    return function(*arguments) if function else None
