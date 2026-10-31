"""SpyGlass lint integration."""

from backends import tcl_value

BACKEND = {
    "tool": "spyglass",
    "version_args": ["-version"],
    "format": "flist-plus",
    "script": "spyglass.tcl",
    "environment": {"RTL_FILELIST": "{inputs}/sources.f"},
    "commands": [
        [
            "spyglass",
            "-project",
            "{inputs}/spyglass.prj",
            "-goals",
            "lint/lint_rtl",
            "-batch",
            "{options}",
        ]
    ],
    "outputs": ["{reports}/summary.rpt"],
}


def prepare(config, entry, root, directory, source):
    return {"spyglass.prj": f"source {tcl_value(entry['settings']['script'])}\n"}


def collect(config, entry, directory, snapshot):
    import shutil

    for name in ("html_reports", "consolidated_reports"):
        source = directory / "work/spyglass" / name
        if source.is_dir():
            shutil.copytree(source, directory / "reports" / name, dirs_exist_ok=True)
    reports = list((directory / "work").rglob("moresimple.rpt"))
    if reports:
        shutil.copyfile(reports[0], directory / "reports/summary.rpt")
