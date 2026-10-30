"""Verilator lint integration."""

BACKEND = {
    "tool": "verilator",
    "version_args": ["--version"],
    "format": "verilator",
    "commands": [
        [
            "verilator",
            "--lint-only",
            "--top-module",
            "{top}",
            "--Mdir",
            "{work}/verilator",
            "{options}",
            "-f",
            "{inputs}/sources.f",
        ]
    ],
    "outputs": ["{reports}/summary.rpt"],
}
