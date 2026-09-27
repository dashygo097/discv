#pragma once

#include "demu/generated/cfg.hh"
#include <cstddef>
#include <cstdint>

namespace demu {

static_assert(generated::XLEN == 32,
              "The project-specific DEMU integration supports RV32 only");

using addr_t = std::uint32_t;
using byte_t = std::uint8_t;
using instr_t = std::uint32_t;
using word_t = std::uint32_t;

inline constexpr std::size_t NUM_ARCH_REGS = 32;

} // namespace demu
