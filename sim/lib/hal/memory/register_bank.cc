#include "demu/hal/memory/register_bank.hh"
#include "demu/logger.hh"

namespace demu::hal::memory {

RegisterBank::RegisterBank(MemoryAllocator &memory) : memory_(memory) {}

auto RegisterBank::add(const RegisterDescriptor &descriptor) noexcept -> bool {
  if ((descriptor.offset_ % sizeof(word_t)) != 0) {
    HAL_WARN("Register offset 0x{:x} is not word-aligned", descriptor.offset_)
    return false;
  }

  const auto wide_address =
      static_cast<std::uint64_t>(memory_.base_address()) + descriptor.offset_;
  if (wide_address > static_cast<std::uint64_t>(~addr_t{0})) {
    HAL_WARN("Register offset 0x{:x} overflows the address space",
             descriptor.offset_)
    return false;
  }

  const auto address = static_cast<addr_t>(wide_address);
  if (!memory_.is_valid_range(address, sizeof(word_t))) {
    HAL_WARN("Register offset 0x{:x} is outside MMIO range", descriptor.offset_)
    return false;
  }

  const auto [_, inserted] = registers_.emplace(descriptor.offset_, descriptor);
  if (!inserted) {
    HAL_WARN("Register offset 0x{:x} is already defined", descriptor.offset_)
    return false;
  }

  memory_.write_word(address, descriptor.reset_value_);
  return true;
}

auto RegisterBank::access(const Transaction &transaction) noexcept -> Response {
  if ((transaction.address % sizeof(word_t)) != 0) {
    return Response{ResponseStatus::Misaligned};
  }
  if (transaction.size != sizeof(word_t)) {
    return Response{ResponseStatus::Unsupported};
  }
  if (!memory_.is_valid_range(transaction.address, sizeof(word_t))) {
    return Response{ResponseStatus::DecodeError};
  }

  const auto offset = memory_.to_offset(transaction.address);
  const auto found = registers_.find(offset);
  if (found == registers_.end()) {
    return Response{ResponseStatus::DecodeError};
  }

  const auto &descriptor = found->second;
  if (transaction.access == AccessType::Read) {
    if (descriptor.access_ == RegisterAccess::WriteOnly) {
      return Response{ResponseStatus::Unsupported};
    }
    return Response{ResponseStatus::Okay,
                    memory_.read_word(transaction.address)};
  }

  if (descriptor.access_ == RegisterAccess::ReadOnly) {
    return Response{ResponseStatus::Unsupported};
  }

  constexpr auto valid_strobe =
      static_cast<byte_t>((word_t{1} << sizeof(word_t)) - 1);
  if ((transaction.strobe & ~valid_strobe) != 0) {
    return Response{ResponseStatus::SlaveError};
  }

  word_t byte_mask = 0;
  for (std::uint32_t byte = 0; byte < sizeof(word_t); ++byte) {
    if ((transaction.strobe & (byte_t{1} << byte)) != 0) {
      byte_mask |= word_t{0xFF} << (byte * 8U);
    }
  }

  const auto write_mask = descriptor.writable_mask_ & byte_mask;
  const auto current = memory_.read_word(transaction.address);
  const auto value = (current & ~write_mask) | (transaction.data & write_mask);
  memory_.write_word(transaction.address, value);
  return Response{};
}

void RegisterBank::reset() noexcept {
  memory_.clear();
  for (const auto &[offset, descriptor] : registers_) {
    memory_.write_word(register_address(offset), descriptor.reset_value_);
  }
}

auto RegisterBank::value(addr_t offset) const noexcept -> word_t {
  const auto found = registers_.find(offset);
  if (found == registers_.end()) {
    HAL_WARN("Register offset 0x{:x} is not defined", offset)
    return 0;
  }
  return memory_.read_word(register_address(offset));
}

auto RegisterBank::write_value(addr_t offset, word_t value) noexcept -> bool {
  if (registers_.find(offset) == registers_.end()) {
    HAL_WARN("Register offset 0x{:x} is not defined", offset)
    return false;
  }
  memory_.write_word(register_address(offset), value);
  return true;
}

auto RegisterBank::register_address(addr_t offset) const noexcept -> addr_t {
  return memory_.base_address() + offset;
}

} // namespace demu::hal::memory
