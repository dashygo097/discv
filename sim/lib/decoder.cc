#include "demu/decoder.hh"
#include "demu/generated/cfg.hh"
#include <iomanip>
#include <sstream>

namespace demu {

namespace {

constexpr std::uint8_t OPCODE_LOAD = 0x03;
constexpr std::uint8_t OPCODE_MISC_MEM = 0x0F;
constexpr std::uint8_t OPCODE_OP_IMM = 0x13;
constexpr std::uint8_t OPCODE_AUIPC = 0x17;
constexpr std::uint8_t OPCODE_STORE = 0x23;
constexpr std::uint8_t OPCODE_OP = 0x33;
constexpr std::uint8_t OPCODE_LUI = 0x37;
constexpr std::uint8_t OPCODE_BRANCH = 0x63;
constexpr std::uint8_t OPCODE_JALR = 0x67;
constexpr std::uint8_t OPCODE_JAL = 0x6F;
constexpr std::uint8_t OPCODE_SYSTEM = 0x73;

constexpr instr_t ECALL = 0x00000073;
constexpr instr_t EBREAK = 0x00100073;

[[nodiscard]] constexpr auto sign_extend(std::uint32_t value,
                                         unsigned width) noexcept
    -> std::int32_t {
  const auto sign = std::uint32_t{1} << (width - 1U);
  return static_cast<std::int32_t>((value ^ sign) - sign);
}

[[nodiscard]] auto fence_set(std::uint8_t value) -> std::string {
  std::string result;
  if ((value & 0x8U) != 0) {
    result += 'i';
  }
  if ((value & 0x4U) != 0) {
    result += 'o';
  }
  if ((value & 0x2U) != 0) {
    result += 'r';
  }
  if ((value & 0x1U) != 0) {
    result += 'w';
  }
  return result.empty() ? "0" : result;
}

} // namespace

Decoder::Decoder(instr_t instruction) noexcept : instruction_(instruction) {
  decode();
}

void Decoder::decode() noexcept {
  opcode_ = static_cast<std::uint8_t>(instruction_ & 0x7FU);
  rd_ = static_cast<std::uint8_t>((instruction_ >> 7U) & 0x1FU);
  funct3_ = static_cast<std::uint8_t>((instruction_ >> 12U) & 0x07U);
  rs1_ = static_cast<std::uint8_t>((instruction_ >> 15U) & 0x1FU);
  rs2_ = static_cast<std::uint8_t>((instruction_ >> 20U) & 0x1FU);
  funct7_ = static_cast<std::uint8_t>((instruction_ >> 25U) & 0x7FU);

  switch (type()) {
  case InstructionType::I:
    immediate_ = decode_i_immediate();
    break;
  case InstructionType::S:
    immediate_ = decode_s_immediate();
    break;
  case InstructionType::B:
    immediate_ = decode_b_immediate();
    break;
  case InstructionType::U:
    immediate_ = decode_u_immediate();
    break;
  case InstructionType::J:
    immediate_ = decode_j_immediate();
    break;
  default:
    immediate_ = 0;
    break;
  }
}

auto Decoder::type() const noexcept -> InstructionType {
  switch (opcode_) {
  case OPCODE_OP:
    return InstructionType::R;
  case OPCODE_OP_IMM:
  case OPCODE_LOAD:
  case OPCODE_JALR:
    return InstructionType::I;
  case OPCODE_STORE:
    return InstructionType::S;
  case OPCODE_BRANCH:
    return InstructionType::B;
  case OPCODE_LUI:
  case OPCODE_AUIPC:
    return InstructionType::U;
  case OPCODE_JAL:
    return InstructionType::J;
  case OPCODE_MISC_MEM:
    return InstructionType::Fence;
  case OPCODE_SYSTEM:
    return InstructionType::System;
  default:
    return InstructionType::Unknown;
  }
}

auto Decoder::mnemonic() const noexcept -> std::string_view {
  switch (opcode_) {
  case OPCODE_OP:
    if (funct7_ == 0x01 && generated::HAS_M) {
      switch (funct3_) {
      case 0x0:
        return "mul";
      case 0x1:
        return "mulh";
      case 0x2:
        return "mulhsu";
      case 0x3:
        return "mulhu";
      case 0x4:
        return "div";
      case 0x5:
        return "divu";
      case 0x6:
        return "rem";
      case 0x7:
        return "remu";
      }
    }
    switch (funct3_) {
    case 0x0:
      return funct7_ == 0x00 ? "add" : funct7_ == 0x20 ? "sub" : "unknown";
    case 0x1:
      return funct7_ == 0x00 ? "sll" : "unknown";
    case 0x2:
      return funct7_ == 0x00 ? "slt" : "unknown";
    case 0x3:
      return funct7_ == 0x00 ? "sltu" : "unknown";
    case 0x4:
      return funct7_ == 0x00 ? "xor" : "unknown";
    case 0x5:
      return funct7_ == 0x00 ? "srl" : funct7_ == 0x20 ? "sra" : "unknown";
    case 0x6:
      return funct7_ == 0x00 ? "or" : "unknown";
    case 0x7:
      return funct7_ == 0x00 ? "and" : "unknown";
    }
    break;

  case OPCODE_OP_IMM:
    switch (funct3_) {
    case 0x0:
      return "addi";
    case 0x1:
      return funct7_ == 0x00 ? "slli" : "unknown";
    case 0x2:
      return "slti";
    case 0x3:
      return "sltiu";
    case 0x4:
      return "xori";
    case 0x5:
      return funct7_ == 0x00 ? "srli" : funct7_ == 0x20 ? "srai" : "unknown";
    case 0x6:
      return "ori";
    case 0x7:
      return "andi";
    }
    break;

  case OPCODE_LOAD:
    switch (funct3_) {
    case 0x0:
      return "lb";
    case 0x1:
      return "lh";
    case 0x2:
      return "lw";
    case 0x4:
      return "lbu";
    case 0x5:
      return "lhu";
    }
    break;

  case OPCODE_STORE:
    switch (funct3_) {
    case 0x0:
      return "sb";
    case 0x1:
      return "sh";
    case 0x2:
      return "sw";
    }
    break;

  case OPCODE_BRANCH:
    switch (funct3_) {
    case 0x0:
      return "beq";
    case 0x1:
      return "bne";
    case 0x4:
      return "blt";
    case 0x5:
      return "bge";
    case 0x6:
      return "bltu";
    case 0x7:
      return "bgeu";
    }
    break;

  case OPCODE_LUI:
    return "lui";
  case OPCODE_AUIPC:
    return "auipc";
  case OPCODE_JAL:
    return "jal";
  case OPCODE_JALR:
    return funct3_ == 0 ? "jalr" : "unknown";

  case OPCODE_MISC_MEM:
    if (funct3_ == 0) {
      return "fence";
    }
    if (funct3_ == 1 && generated::HAS_ZIFENCEI) {
      return "fence.i";
    }
    break;

  case OPCODE_SYSTEM:
    if (instruction_ == ECALL) {
      return "ecall";
    }
    if (instruction_ == EBREAK) {
      return "ebreak";
    }
    if (generated::HAS_ZICSR) {
      switch (funct3_) {
      case 0x1:
        return "csrrw";
      case 0x2:
        return "csrrs";
      case 0x3:
        return "csrrc";
      case 0x5:
        return "csrrwi";
      case 0x6:
        return "csrrsi";
      case 0x7:
        return "csrrci";
      }
    }
    break;
  }

  return "unknown";
}

auto Decoder::to_string() const -> std::string {
  std::ostringstream stream;
  const auto name = mnemonic();
  stream << std::left << std::setw(8) << name;

  if (name == "unknown") {
    stream << "0x" << std::right << std::hex << std::setw(8)
           << std::setfill('0') << instruction_;
    return stream.str();
  }

  switch (type()) {
  case InstructionType::R:
    stream << 'x' << static_cast<unsigned>(rd_) << ", x"
           << static_cast<unsigned>(rs1_) << ", x"
           << static_cast<unsigned>(rs2_);
    break;

  case InstructionType::I:
    if (opcode_ == OPCODE_LOAD || opcode_ == OPCODE_JALR) {
      stream << 'x' << static_cast<unsigned>(rd_) << ", " << immediate_ << "(x"
             << static_cast<unsigned>(rs1_) << ')';
    } else {
      const auto displayed_immediate = funct3_ == 0x1 || funct3_ == 0x5
                                           ? static_cast<std::int32_t>(rs2_)
                                           : immediate_;
      stream << 'x' << static_cast<unsigned>(rd_) << ", x"
             << static_cast<unsigned>(rs1_) << ", " << displayed_immediate;
    }
    break;

  case InstructionType::S:
    stream << 'x' << static_cast<unsigned>(rs2_) << ", " << immediate_ << "(x"
           << static_cast<unsigned>(rs1_) << ')';
    break;

  case InstructionType::B:
    stream << 'x' << static_cast<unsigned>(rs1_) << ", x"
           << static_cast<unsigned>(rs2_) << ", " << immediate_;
    break;

  case InstructionType::U:
    stream << 'x' << static_cast<unsigned>(rd_) << ", 0x" << std::right
           << std::hex << std::setw(8) << std::setfill('0')
           << static_cast<std::uint32_t>(immediate_);
    break;

  case InstructionType::J:
    stream << 'x' << static_cast<unsigned>(rd_) << ", " << immediate_;
    break;

  case InstructionType::Fence:
    if (funct3_ == 0) {
      const auto predecessor =
          static_cast<std::uint8_t>((instruction_ >> 24U) & 0x0FU);
      const auto successor =
          static_cast<std::uint8_t>((instruction_ >> 20U) & 0x0FU);
      stream << fence_set(predecessor) << ", " << fence_set(successor);
    }
    break;

  case InstructionType::System:
    if (instruction_ != ECALL && instruction_ != EBREAK) {
      const auto csr = (instruction_ >> 20U) & 0x0FFFU;
      stream << 'x' << static_cast<unsigned>(rd_) << ", 0x" << std::right
             << std::hex << std::setw(3) << std::setfill('0') << csr << ", ";
      if (funct3_ < 0x5) {
        stream << 'x' << std::dec << static_cast<unsigned>(rs1_);
      } else {
        stream << std::dec << static_cast<unsigned>(rs1_);
      }
    }
    break;

  case InstructionType::Unknown:
    break;
  }

  return stream.str();
}

auto Decoder::decode_i_immediate() const noexcept -> std::int32_t {
  return sign_extend((instruction_ >> 20U) & 0x0FFFU, 12);
}

auto Decoder::decode_s_immediate() const noexcept -> std::int32_t {
  const auto value =
      ((instruction_ >> 7U) & 0x1FU) | ((instruction_ >> 20U) & 0x0FE0U);
  return sign_extend(value, 12);
}

auto Decoder::decode_b_immediate() const noexcept -> std::int32_t {
  const auto value =
      ((instruction_ >> 7U) & 0x001EU) | ((instruction_ >> 20U) & 0x07E0U) |
      ((instruction_ << 4U) & 0x0800U) | ((instruction_ >> 19U) & 0x1000U);
  return sign_extend(value, 13);
}

auto Decoder::decode_u_immediate() const noexcept -> std::int32_t {
  return static_cast<std::int32_t>(instruction_ & 0xFFFFF000U);
}

auto Decoder::decode_j_immediate() const noexcept -> std::int32_t {
  const auto value =
      ((instruction_ >> 20U) & 0x07FEU) | ((instruction_ >> 9U) & 0x0800U) |
      (instruction_ & 0x0FF000U) | ((instruction_ >> 11U) & 0x100000U);
  return sign_extend(value, 21);
}

} // namespace demu
