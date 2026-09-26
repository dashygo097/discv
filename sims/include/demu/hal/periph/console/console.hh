#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/mmio_target.hh"

namespace demu::hal::periph::console {
class Console : public Device, public MmioTarget {
public:
  explicit Console(const DeviceDescriptor &desc);

  void clock_tick() override;
  void reset() override;

  [[nodiscard]] auto submit(transaction_id_t,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override;

private:
};
} // namespace demu::hal::periph::console
