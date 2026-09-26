#include "demu/hal/periph/host_exit/host_exit.hh"

namespace demu::hal::periph::host_exit {

HostExit::HostExit(const DeviceDescriptor &desc) : Device(desc) {}

void HostExit::clock_tick() {}

void HostExit::reset() {}

auto HostExit::submit(transaction_id_t,
                      const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.access != AccessType::Write ||
      transaction.address != base_address() ||
      transaction.size != sizeof(word_t) ||
      transaction.strobe != byte_t{0x0F}) {
    return Response{ResponseStatus::SlaveError};
  }
  return Response{ResponseStatus::Okay, 0,
                  DeviceEvent{DeviceEventType::Exit, transaction.data}};
}

} // namespace demu::hal::periph::host_exit
