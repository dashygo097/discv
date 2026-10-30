"""Design Compiler integration. Synthesis policy is implemented in dc.tcl."""

BACKEND = {
    "tool": "dc_shell",
    "version_args": ["-version"],
    "format": "synopsys",
    "script": "dc.tcl",
    "technology_inputs": [
        "dc.target_libraries",
        "dc.link_libraries",
        "dc.synthetic_libraries",
        "dc.library_pairs",
        "dc.setup_scripts",
    ],
    "commands": [["dc_shell", "{options}", "-f", "{script}"]],
    "outputs": [
        "{reports}/summary.rpt",
        "{results}/{top}.v",
        "{results}/{top}.ddc",
        "{results}/{top}.sdc",
        "{results}/{top}.svf",
    ],
    "defaults": {
        "compile": "ultra",
        "preserve_hierarchy": True,
        "retime": False,
        "clock_gating": False,
    },
}
