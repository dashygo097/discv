"""RISC-V configuration generator owned by this design project."""

import re

from project_config import (
    ConfigError,
    config_digest,
    header,
    reject_unknown,
    require_string,
    unsigned_integer,
)

GENERATOR = {"sources": [{"files": ["arch_pkg.sv"]}]}

RISCV_MARCH = re.compile(
    r"^rv(?P<xlen>32|64)(?P<compact>[a-z0-9]+)"
    r"(?P<suffix>(?:_[a-z][a-z0-9]*)*)$"
)

RISCV_SINGLE_EXTENSION = re.compile(r"(?P<name>[a-z])(?P<version>\d+(?:p\d+)?)?")

RISCV_MULTI_EXTENSION = re.compile(r"^(?P<name>[a-z][a-z0-9]*?)(?:\d+(?:p\d+)?)?$")

ARCH_FEATURES = (
    "i",
    "e",
    "m",
    "a",
    "f",
    "d",
    "c",
    "b",
    "v",
    "zicsr",
    "zifencei",
)


def parse_riscv_march(march):
    match = RISCV_MARCH.fullmatch(march)
    if match is None:
        raise ConfigError(
            "architecture.march: expected a lowercase GCC-style RISC-V ISA "
            'string such as "rv32i" or "rv64gc"'
        )

    compact = match.group("compact")
    single_extensions = []
    offset = 0
    while offset < len(compact):
        extension_match = RISCV_SINGLE_EXTENSION.match(compact, offset)
        if extension_match is None:
            raise ConfigError(
                f"architecture.march: malformed extension near {compact[offset:]!r}"
            )
        single_extensions.append(extension_match.group("name"))
        offset = extension_match.end()

    duplicate_single_extensions = sorted(
        extension
        for extension in set(single_extensions)
        if single_extensions.count(extension) > 1
    )
    if duplicate_single_extensions:
        raise ConfigError(
            "architecture.march: duplicate single-letter extension(s): "
            + ", ".join(duplicate_single_extensions)
        )

    base = single_extensions[0]
    if base not in {"i", "e", "g"}:
        raise ConfigError('architecture.march: base ISA must be "i", "e", or "g"')
    if "g" in single_extensions[1:]:
        raise ConfigError('architecture.march: "g" is only valid as the base ISA')

    extensions = set(single_extensions)
    if base == "g":
        extensions.remove("g")
        extensions.update({"i", "m", "a", "f", "d", "zicsr", "zifencei"})

    suffix = match.group("suffix")
    for token in suffix.split("_"):
        if not token:
            continue
        extension_match = RISCV_MULTI_EXTENSION.fullmatch(token)
        if extension_match is None:
            raise ConfigError(
                f"architecture.march: malformed multi-letter extension: {token}"
            )
        extension = extension_match.group("name")
        if extension in extensions:
            raise ConfigError(f"architecture.march: duplicate extension: {extension}")
        extensions.add(extension)

    xlen = int(match.group("xlen"))
    if xlen != 32 and "e" in extensions:
        raise ConfigError("architecture.march: the E base ISA requires RV32")
    if "i" in extensions and "e" in extensions:
        raise ConfigError('architecture.march: base ISAs "i" and "e" conflict')
    return xlen, frozenset(extensions)


def configure(settings, root):
    reject_unknown(
        settings, {"generator", "march", "reset_vector", "_generator"}, "architecture"
    )
    march = require_string(settings, "march", "architecture")
    xlen, extensions = parse_riscv_march(march)
    settings.update(
        xlen=xlen,
        extensions=sorted(extensions),
        features={
            feature: feature in extensions
            for feature in sorted(set(ARCH_FEATURES) | extensions)
        },
        reset_vector=unsigned_integer(
            settings.get("reset_vector"),
            "architecture.reset_vector",
            maximum=(1 << xlen) - 1,
        ),
    )


def generate(config, settings, root):
    return {"arch_pkg.sv": render_arch_package(settings, config_digest(settings))}


def render_arch_package(architecture, digest):
    lines = [
        header("//", digest).rstrip(),
        "package arch_pkg;",
        "  typedef struct packed {",
        "    int unsigned xlen;",
        "    logic [63:0] reset_vector;",
        *[f"    logic has_{feature};" for feature in architecture["features"]],
        "  } arch_t;",
        "",
        f"  localparam int unsigned XLEN = 32'd{architecture['xlen']};",
        "  localparam logic [63:0] RESET_VECTOR = "
        f"64'h{architecture['reset_vector']:016x};",
        "  localparam arch_t ARCH = '{",
        "      xlen: XLEN,",
        "      reset_vector: RESET_VECTOR,",
        *[
            f"      has_{feature}: 1'b{int(architecture['features'][feature])},"
            for feature in architecture["features"]
        ],
        "      default: '0",
        "  };",
        "endpackage",
    ]
    return "\n".join(lines) + "\n"
