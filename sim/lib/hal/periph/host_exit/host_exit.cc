#include "demu/hal/periph/host_exit/host_exit.hh"

namespace demu::hal::periph::host_exit {

HostExit::HostExit(const DeviceDescriptor &desc)
    : Device(desc.name, desc.type), MmioTarget(static_cast<addr_t>(desc.base),
                                               static_cast<size_t>(desc.size)) {
}

void HostExit::clock_tick() {}

void HostExit::reset() { memory().clear(); }

auto HostExit::submit(transaction_id_t, const Transaction &transaction) noexcept
    -> std::optional<Response> {
  if (transaction.access != AccessType::Write) {
    return Response{ResponseStatus::Unsupported};
  }

  if (transaction.address != base_address() ||
      transaction.size != sizeof(word_t) ||
      transaction.strobe != byte_t{0x0F}) {
    return Response{ResponseStatus::SlaveError};
  }

  memory().write_word(transaction.address, transaction.data);

  return Response{ResponseStatus::Okay, 0,
                  DeviceEvent{DeviceEventType::Exit,
                              memory().read_word(transaction.address)}};
}

} // namespace demu::hal::periph::host_exit
