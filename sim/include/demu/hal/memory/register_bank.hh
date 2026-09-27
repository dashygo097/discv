#pragma once

#include "demu/hal/memory/allocator.hh"
#include "demu/hal/transaction.hh"
#include <cstdint>
#include <map>

namespace demu::hal::memory {

enum class RegisterAccess : std::uint8_t {
  ReadOnly,
  WriteOnly,
  ReadWrite,
};

class RegisterDescriptor final {
public:
  auto offset(addr_t value) noexcept -> RegisterDescriptor & {
    offset_ = value;
    return *this;
  }

  auto reset_value(word_t value) noexcept -> RegisterDescriptor & {
    reset_value_ = value;
    return *this;
  }

  auto writable_mask(word_t value) noexcept -> RegisterDescriptor & {
    writable_mask_ = value;
    return *this;
  }

  auto readonly() noexcept -> RegisterDescriptor & {
    access_ = RegisterAccess::ReadOnly;
    return *this;
  }

  auto writeonly() noexcept -> RegisterDescriptor & {
    access_ = RegisterAccess::WriteOnly;
    return *this;
  }

  auto readwrite() noexcept -> RegisterDescriptor & {
    access_ = RegisterAccess::ReadWrite;
    return *this;
  }

private:
  friend class RegisterBank;

  addr_t offset_{0};
  word_t reset_value_{0};
  word_t writable_mask_{~word_t{0}};
  RegisterAccess access_{RegisterAccess::ReadWrite};
};

class RegisterBank final {
public:
  explicit RegisterBank(MemoryAllocator &memory);

  [[nodiscard]] auto add(const RegisterDescriptor &descriptor) noexcept -> bool;
  [[nodiscard]] auto access(const Transaction &transaction) noexcept
      -> Response;

  void reset() noexcept;

  [[nodiscard]] auto value(addr_t offset) const noexcept -> word_t;
  auto write_value(addr_t offset, word_t value) noexcept -> bool;

private:
  [[nodiscard]] auto register_address(addr_t offset) const noexcept -> addr_t;

  MemoryAllocator &memory_;
  std::map<addr_t, RegisterDescriptor> registers_;
};

} // namespace demu::hal::memory
