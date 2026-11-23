#include "demu/hal/periph/boot_rom/boot_rom.hh"

namespace demu::hal::periph::boot_rom {

BootROM::BootROM(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)) {
}

auto BootROM::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.size != sizeof(word_t)) {
    return Response{ResponseStatus::Unsupported};
  }

  const addr_t address = transaction.address & ~addr_t{sizeof(word_t) - 1};
  if (!memory().is_valid_range(address, sizeof(word_t))) {
    return Response{ResponseStatus::DecodeError};
  }
  if (transaction.access == AccessType::Write) {
    return Response{ResponseStatus::SlaveError};
  }
  return Response{ResponseStatus::Okay, memory().read_word(address)};
}

} // namespace demu::hal::periph::boot_rom
