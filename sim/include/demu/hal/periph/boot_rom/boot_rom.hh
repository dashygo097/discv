#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/mmio_target.hh"

namespace demu::hal::periph::boot_rom {

class BootROM final : public Device, public MmioTarget {
public:
  explicit BootROM(const DeviceDescriptor &desc);

  void clock_tick() override {}
  void reset() override {}

  [[nodiscard]] auto submit(transaction_id_t,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override;
};

} // namespace demu::hal::periph::boot_rom
