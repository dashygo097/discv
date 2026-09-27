#include "demu/hal/periph/console/console.hh"
#include <cstdint>

namespace demu::hal::periph::console {

Console::Console(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)),
      registers_(memory()) {
  (void)registers_.add(memory::RegisterDescriptor{}
                           .offset(DATA_OFFSET)
                           .reset_value(0)
                           .writeonly());
}

void Console::clock_tick() {}

void Console::reset() { registers_.reset(); }

auto Console::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  auto response = registers_.access(transaction);
  if (response.error()) {
    return response;
  }

  bool character_written = false;
  byte_t character = 0;
  for (std::uint32_t byte = 0; byte < sizeof(word_t); ++byte) {
    if ((transaction.strobe & (byte_t{1} << byte)) == 0) {
      continue;
    }

    const auto value = static_cast<byte_t>(transaction.data >> (byte * 8U));
    if (!character_written) {
      character = value;
      character_written = true;
    }
  }

  if (!character_written) {
    return Response{ResponseStatus::SlaveError};
  }

  response.event = DeviceEvent{DeviceEventType::ConsoleWrite,
                               static_cast<word_t>(character)};
  return response;
}

} // namespace demu::hal::periph::console
