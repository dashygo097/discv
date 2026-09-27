#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/memory/register_bank.hh"
#include "demu/hal/mmio_target.hh"

namespace demu::hal::periph::host_exit {

class HostExit final : public Device, public MmioTarget {
public:
  explicit HostExit(const DeviceDescriptor &desc);

  void clock_tick() override;
  void reset() override;

  [[nodiscard]] auto submit(transaction_id_t,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override;

private:
  static constexpr addr_t EXIT_CODE_OFFSET = 0;

  memory::RegisterBank registers_;
};

} // namespace demu::hal::periph::host_exit
