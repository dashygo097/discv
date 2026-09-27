#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/mmio_target.hh"
#include "demu/hal/platform.hh"
#include "demu/hal/transaction.hh"
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace demu::hal {

class DeviceManager final {
public:
  DeviceManager() = default;
  ~DeviceManager() = default;

  DeviceManager(const DeviceManager &) = delete;
  auto operator=(const DeviceManager &) -> DeviceManager & = delete;
  DeviceManager(DeviceManager &&) = delete;
  auto operator=(DeviceManager &&) -> DeviceManager & = delete;

  auto configure() -> bool;
  auto load_binary(const std::string &filename) -> bool;

  [[nodiscard]] auto get_device_by_name(std::string_view name) noexcept
      -> Device *;
  [[nodiscard]] auto get_device_by_name(std::string_view name) const noexcept
      -> const Device *;
  [[nodiscard]] auto find_mmio_target(addr_t address) noexcept -> MmioTarget *;
  [[nodiscard]] auto find_mmio_target(addr_t address) const noexcept
      -> const MmioTarget *;

  [[nodiscard]] auto submit(port_id_t port,
                            const Transaction &transaction) noexcept
      -> std::optional<transaction_id_t>;
  [[nodiscard]] auto poll(transaction_id_t transaction) noexcept
      -> std::optional<Response>;
  auto complete(transaction_id_t transaction) noexcept -> bool;

  [[nodiscard]] auto exit_requested() const noexcept -> bool {
    return exit_requested_;
  }
  [[nodiscard]] auto exit_code() const noexcept -> word_t { return exit_code_; }

  void reset() noexcept;
  void clock_tick() noexcept;
  void dump_mmio_map() const;

private:
  struct DeviceSlot {
    std::unique_ptr<Device> device;
    MmioTarget *mmio;
    bool load;
    addr_t load_address;
  };

  struct PendingTransaction {
    MmioTarget *target;
    Transaction request;
    std::optional<Response> response;
  };

  void handle_event(const DeviceEvent &event) noexcept;

  std::vector<PortDescriptor> ports_;
  std::vector<DeviceSlot> devices_;
  std::map<addr_t, device_id_t> mmio_map_;
  std::unordered_map<std::string, device_id_t> name_indices_;
  std::unordered_map<transaction_id_t, PendingTransaction> pending_;
  transaction_id_t next_transaction_{1};
  bool exit_requested_{false};
  word_t exit_code_{0};
};

} // namespace demu::hal
