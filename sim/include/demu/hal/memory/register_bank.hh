#pragma once

#include "demu/hal/memory/allocator.hh"

namespace demu::hal::memory {

class RegisterBank final {
public:
  explicit RegisterBank(MemoryAllocator &memory);

private:
  MemoryAllocator &memory_;
};

} // namespace demu::hal::memory
