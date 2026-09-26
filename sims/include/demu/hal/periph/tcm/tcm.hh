#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/mmio_target.hh"

namespace demu::hal::periph::tcm {

class TCM final : public Device, public MmioTarget {
public:
  explicit TCM(const DeviceDescriptor &desc)
      : Device(desc.name, desc.type),
        MmioTarget(static_cast<addr_t>(desc.base),
                   static_cast<size_t>(desc.size)) {}

  ~TCM() override = default;

  [[nodiscard]] auto submit(transaction_id_t id,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override;

  void clock_tick() override;
  void reset() override;
  void dump(addr_t start, size_t size) const noexcept override;
};

} // namespace demu::hal::periph::tcm
