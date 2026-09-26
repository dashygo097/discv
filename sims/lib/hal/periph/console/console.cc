#include "demu/hal/periph/console/console.hh"
namespace demu::hal::periph::console {

Console::Console(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)) {
}

void Console::clock_tick() {}

void Console::reset() {}

auto Console::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.access != AccessType::Write) {
    return Response{ResponseStatus::Unsupported};
  }

  return Response{ResponseStatus::Okay, 0,
                  DeviceEvent{DeviceEventType::Exit, transaction.data}};
}

} // namespace demu::hal::periph::console
