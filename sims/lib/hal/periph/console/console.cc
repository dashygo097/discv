#include "demu/hal/periph/console/console.hh"
#include <cstdint>
#include <cstdio>

namespace demu::hal::periph::console {

Console::Console(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)) {
}

void Console::clock_tick() {}

void Console::reset() { memory().clear(); }

auto Console::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.access != AccessType::Write) {
    return Response{ResponseStatus::Unsupported};
  }
  if (transaction.size != sizeof(word_t)) {
    return Response{ResponseStatus::Unsupported};
  }

  const addr_t aligned_address = transaction.address & ~addr_t{0x3U};
  if (!memory().is_valid_range(aligned_address, sizeof(word_t))) {
    return Response{ResponseStatus::DecodeError};
  }

  bool character_written = false;
  byte_t character = 0;
  for (std::uint32_t byte = 0; byte < sizeof(word_t); ++byte) {
    if ((transaction.strobe & (byte_t{1} << byte)) == 0) {
      continue;
    }

    const auto value = static_cast<byte_t>(transaction.data >> (byte * 8U));
    memory().write_byte(aligned_address + byte, value);
    if (!character_written) {
      character = value;
      character_written = true;
    }
  }

  if (!character_written) {
    return Response{ResponseStatus::SlaveError};
  }

  std::fputc(static_cast<int>(character), stdout);
  std::fflush(stdout);

  return Response{};
}

} // namespace demu::hal::periph::console
