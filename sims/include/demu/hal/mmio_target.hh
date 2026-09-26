#pragma once

#include "demu/hal/allocator.hh"
#include "demu/hal/platform.hh"
#include "demu/hal/transaction.hh"
#include <optional>
#include <string>

namespace demu::hal {

class MmioTarget {
public:
  MmioTarget(addr_t base_address, size_t size) : memory_(base_address, size) {}

  virtual ~MmioTarget() = default;

  MmioTarget(const MmioTarget &) = delete;
  auto operator=(const MmioTarget &) -> MmioTarget & = delete;
  MmioTarget(MmioTarget &&) = delete;
  auto operator=(MmioTarget &&) -> MmioTarget & = delete;

  [[nodiscard]] auto base_address() const noexcept -> addr_t {
    return memory_.base_address();
  }
  [[nodiscard]] auto size() const noexcept -> size_t { return memory_.size(); }
  [[nodiscard]] auto owns_address(addr_t address) const noexcept -> bool {
    return memory_.is_valid_addr(address);
  }

  [[nodiscard]] auto memory() noexcept -> MemoryAllocator & { return memory_; }
  [[nodiscard]] auto memory() const noexcept -> const MemoryAllocator & {
    return memory_;
  }

  auto load_binary(const std::string &filename, addr_t address) -> bool {
    return memory_.load_binary(filename, address);
  }
  virtual void dump(addr_t start, size_t size) const noexcept {
    memory_.dump(start, static_cast<addr_t>(size));
  }

  [[nodiscard]] virtual auto submit(transaction_id_t id,
                                    const Transaction &transaction) noexcept
      -> std::optional<Response> = 0;

  [[nodiscard]] virtual auto poll(transaction_id_t) noexcept
      -> std::optional<Response> {
    return std::nullopt;
  }

  virtual void complete(transaction_id_t) noexcept {}

private:
  MemoryAllocator memory_;
};

} // namespace demu::hal
