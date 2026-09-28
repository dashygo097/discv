#pragma once

#include "demu/types.hh"
#include <cstdint>
#include <string>
#include <string_view>

namespace demu {

enum class InstructionType : std::uint8_t {
  R,
  I,
  S,
  B,
  U,
  J,
  Fence,
  System,
  Unknown,
};

class Decoder final {
public:
  explicit Decoder(instr_t instruction) noexcept;

  [[nodiscard]] auto type() const noexcept -> InstructionType;
  [[nodiscard]] auto mnemonic() const noexcept -> std::string_view;
  [[nodiscard]] auto to_string() const -> std::string;

  [[nodiscard]] auto instruction() const noexcept -> instr_t {
    return instruction_;
  }
  [[nodiscard]] auto opcode() const noexcept -> std::uint8_t { return opcode_; }
  [[nodiscard]] auto rd() const noexcept -> std::uint8_t { return rd_; }
  [[nodiscard]] auto rs1() const noexcept -> std::uint8_t { return rs1_; }
  [[nodiscard]] auto rs2() const noexcept -> std::uint8_t { return rs2_; }
  [[nodiscard]] auto funct3() const noexcept -> std::uint8_t { return funct3_; }
  [[nodiscard]] auto funct7() const noexcept -> std::uint8_t { return funct7_; }
  [[nodiscard]] auto immediate() const noexcept -> std::int32_t {
    return immediate_;
  }

private:
  void decode() noexcept;

  [[nodiscard]] auto decode_i_immediate() const noexcept -> std::int32_t;
  [[nodiscard]] auto decode_s_immediate() const noexcept -> std::int32_t;
  [[nodiscard]] auto decode_b_immediate() const noexcept -> std::int32_t;
  [[nodiscard]] auto decode_u_immediate() const noexcept -> std::int32_t;
  [[nodiscard]] auto decode_j_immediate() const noexcept -> std::int32_t;

  instr_t instruction_{0};
  std::uint8_t opcode_{0};
  std::uint8_t rd_{0};
  std::uint8_t rs1_{0};
  std::uint8_t rs2_{0};
  std::uint8_t funct3_{0};
  std::uint8_t funct7_{0};
  std::int32_t immediate_{0};
};

} // namespace demu
