#include "demu/hal/periph/host_exit/host_exit.hh"

namespace demu::hal::periph::host_exit {

HostExit::HostExit(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)),
      registers_(memory()) {
  (void)registers_.add(memory::RegisterDescriptor{}
                           .offset(EXIT_CODE_OFFSET)
                           .reset_value(0)
                           .writeonly());
}

void HostExit::clock_tick() {}

void HostExit::reset() { registers_.reset(); }

auto HostExit::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.access == AccessType::Write &&
      transaction.strobe != byte_t{0x0F}) {
    return Response{ResponseStatus::SlaveError};
  }

  auto response = registers_.access(transaction);
  if (response.error()) {
    return response;
  }

  response.event =
      DeviceEvent{DeviceEventType::Exit, registers_.value(EXIT_CODE_OFFSET)};
  return response;
}

} // namespace demu::hal::periph::host_exit
