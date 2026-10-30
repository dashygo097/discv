"""SpyGlass lint integration."""

BACKEND = {
    "tool": "spyglass",
    "version_args": ["-version"],
    "format": "flist-plus",
    "script": "spyglass.tcl",
    "commands": [
        [
            "spyglass",
            "-project",
            "{script}",
            "-goals",
            "lint/lint_rtl",
            "-batch",
            "{options}",
        ]
    ],
    "outputs": ["{reports}/summary.rpt"],
}


def collect(config, entry, directory, snapshot):
    import shutil

    for name in ("html_reports", "consolidated_reports"):
        source = directory / "work/spyglass" / name
        if source.is_dir():
            shutil.copytree(source, directory / "reports" / name, dirs_exist_ok=True)
    reports = list((directory / "work").rglob("moresimple.rpt"))
    if reports:
        shutil.copyfile(reports[0], directory / "reports/summary.rpt")
