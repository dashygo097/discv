#pragma once

#include "demu/hal/allocator.hh"
#include "demu/hal/device.hh"
#include "demu/hal/transaction.hh"
#include <memory>

namespace demu::hal::periph::tcm {

class TCM final : public Device, public MmioTarget {
public:
  explicit TCM(const DeviceDescriptor &desc)
      : Device(desc),
        memory_(std::make_unique<MemoryAllocator>(desc.base, desc.size)) {}

  ~TCM() override = default;

  [[nodiscard]] auto allocator() const noexcept -> MemoryAllocator * override {
    return memory_.get();
  }

  [[nodiscard]] auto submit(transaction_id_t id,
                            const Transaction &transaction) noexcept
      -> std::optional<Response> override;

  void clock_tick() override;
  void reset() override;
  void dump(addr_t start, size_t size) const noexcept override;

private:
  std::unique_ptr<MemoryAllocator> memory_;
};

} // namespace demu::hal::periph::tcm
