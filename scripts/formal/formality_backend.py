"""Formality RTL-to-gate integration."""

BACKEND = {
    "tool": "fm_shell",
    "version_args": ["-version"],
    "format": "formality",
    "script": "formality.tcl",
    "technology_inputs": ["dc.target_libraries", "dc.link_libraries"],
    "commands": [["fm_shell", "{options}", "-f", "{script}"]],
    "outputs": ["{reports}/summary.rpt"],
    "defaults": {"requires": "synth.dc"},
}
