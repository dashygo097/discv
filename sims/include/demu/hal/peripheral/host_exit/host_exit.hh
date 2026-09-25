#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/transaction.hh"

namespace demu::hal::host_exit {

class HostExit final : public Device, public MmioTarget {
public:
  explicit HostExit(const DeviceDescriptor &desc) : Device(desc) {}

  void clock_tick() override {}
  void reset() override {}

  [[nodiscard]] auto submit(transaction_id_t,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override {
    if (transaction.access != AccessType::Write ||
        transaction.address != base_address() ||
        transaction.size != sizeof(word_t) ||
        transaction.strobe != byte_t{0x0F}) {
      return Response{ResponseStatus::SlaveError};
    }
    return Response{ResponseStatus::Okay, 0,
                    DeviceEvent{DeviceEventType::Exit, transaction.data}};
  }
};

} // namespace demu::hal::host_exit
