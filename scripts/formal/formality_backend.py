"""Formality RTL-to-gate integration."""

from backends import configuration_tcl

BACKEND = {
    "tool": "fm_shell",
    "version_args": ["-version"],
    "format": "formality",
    "source": "sources.tcl",
    "inherit_targets": True,
    "script": "formality.tcl",
    "environment": {"STAGE_CONFIG": "{inputs}/backend.tcl"},
    "technology_inputs": ["dc.target_libraries", "dc.link_libraries"],
    "commands": [["fm_shell", "{options}", "-f", "{script}"]],
    "outputs": ["{reports}/summary.rpt"],
    "defaults": {"requires": "synth.dc"},
}


def prepare(config, entry, root, directory, source):
    return {"backend.tcl": configuration_tcl(config, entry)}
