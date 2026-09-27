#include "demu/hal/memory/register_bank.hh"

namespace demu::hal::memory {
RegisterBank::RegisterBank(MemoryAllocator &memory) : memory_(memory) {}

} // namespace demu::hal::memory
