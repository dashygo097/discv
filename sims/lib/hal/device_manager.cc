#include "demu/hal/device_manager.hh"
#include "demu/generated/platform.hh"
#include "demu/hal/periph/host_exit/host_exit.hh"
#include "demu/hal/periph/tcm/tcm.hh"
#include "demu/logger.hh"
#include <utility>

namespace demu::hal {

namespace {

void trace_transaction(const Transaction &transaction,
                       const Response &response) noexcept {
  if (response.error()) {
    return;
  }
  if (transaction.access == AccessType::Write) {
    DEMU_MEM_TRACE("WRITE", transaction.address, transaction.data)
  } else {
    DEMU_MEM_TRACE("READ", transaction.address, response.data)
  }
}

} // namespace

auto DeviceManager::configure() -> bool {
  ports_.clear();
  devices_.clear();
  mmio_map_.clear();
  name_indices_.clear();
  pending_.clear();
  events_.clear();
  next_transaction_ = 1;

  ports_.assign(generated::PORTS.begin(), generated::PORTS.end());
  devices_.reserve(generated::DEVICES.size());

  for (const auto &desc : generated::DEVICES) {
    std::unique_ptr<Device> device;
    switch (desc.type) {
    case DeviceType::TCM:
      device = std::make_unique<periph::tcm::TCM>(desc);
      break;
    case DeviceType::HostExit:
      device = std::make_unique<periph::host_exit::HostExit>(desc);
      break;
    }

    if (!device) {
      HAL_WARN("Invalid device descriptor '{}'", desc.name)
      return false;
    }

    auto *mmio = dynamic_cast<MmioTarget *>(device.get());
    const auto id = static_cast<device_id_t>(devices_.size());

    if (mmio != nullptr) {
      if (mmio->size() == 0) {
        HAL_WARN("MMIO target '{}' has an empty address range", desc.name)
        return false;
      }

      const auto first = mmio->base_address();
      const auto last = first + static_cast<addr_t>(mmio->size() - 1);
      auto next = mmio_map_.lower_bound(first);
      if (next != mmio_map_.end() && next->first <= last) {
        HAL_WARN("MMIO target '{}' overlaps MMIO target '{}'", desc.name,
                 devices_[next->second].device->name())
        return false;
      }
      if (next != mmio_map_.begin()) {
        const auto previous = std::prev(next);
        const auto &previous_slot = devices_[previous->second];
        const auto previous_last = previous->first +
                                   static_cast<addr_t>(
                                       previous_slot.mmio->size() - 1);
        if (previous_last >= first) {
          HAL_WARN("MMIO target '{}' overlaps MMIO target '{}'", desc.name,
                   previous_slot.device->name())
          return false;
        }
      }
      mmio_map_.emplace(first, id);
    } else if (desc.load) {
      HAL_WARN("Load device '{}' is not an MMIO target", desc.name)
      return false;
    }

    name_indices_.emplace(std::string(desc.name), id);
    devices_.push_back(DeviceSlot{std::move(device), mmio, desc.load,
                                  static_cast<addr_t>(desc.load_address)});
  }
  return true;
}

auto DeviceManager::load_binary(const std::string &filename) -> bool {
  for (auto &slot : devices_) {
    if (!slot.load) {
      continue;
    }
    if (slot.mmio == nullptr) {
      HAL_WARN("Load device '{}' has no MMIO target", slot.device->name())
      return false;
    }
    return slot.mmio->load_binary(filename, slot.load_address);
  }
  HAL_WARN("No configured device has a load address")
  return false;
}

auto DeviceManager::get_device_by_name(std::string_view name) noexcept
    -> Device * {
  const auto found = name_indices_.find(std::string(name));
  return found == name_indices_.end() ? nullptr
                                      : devices_[found->second].device.get();
}

auto DeviceManager::get_device_by_name(std::string_view name) const noexcept
    -> const Device * {
  const auto found = name_indices_.find(std::string(name));
  return found == name_indices_.end() ? nullptr
                                      : devices_[found->second].device.get();
}

auto DeviceManager::find_mmio_target(addr_t address) noexcept -> MmioTarget * {
  if (mmio_map_.empty()) {
    return nullptr;
  }
  auto target = mmio_map_.upper_bound(address);
  if (target == mmio_map_.begin()) {
    return nullptr;
  }
  --target;
  auto *mmio = devices_[target->second].mmio;
  return mmio->owns_address(address) ? mmio : nullptr;
}

auto DeviceManager::find_mmio_target(addr_t address) const noexcept
    -> const MmioTarget * {
  if (mmio_map_.empty()) {
    return nullptr;
  }
  auto target = mmio_map_.upper_bound(address);
  if (target == mmio_map_.begin()) {
    return nullptr;
  }
  --target;
  const auto *mmio = devices_[target->second].mmio;
  return mmio->owns_address(address) ? mmio : nullptr;
}

auto DeviceManager::submit(port_id_t port,
                           const Transaction &transaction) noexcept
    -> std::optional<transaction_id_t> {
  if (port >= ports_.size()) {
    HAL_WARN("Transaction targets invalid port {}", port)
    return std::nullopt;
  }

  const auto &port_desc = ports_[port];
  if (port_desc.protocol != BusProtocol::Virt) {
    HAL_WARN("Port '{}' has an unsupported protocol", port_desc.name)
    return std::nullopt;
  }

  auto *target = find_mmio_target(transaction.address);
  const auto id = next_transaction_++;
  if (target == nullptr) {
    HAL_WARN("No MMIO target on '{}' owns address 0x{:08x}", port_desc.name,
             transaction.address)
    pending_.emplace(id, PendingTransaction{
                             nullptr,
                             transaction,
                             Response{ResponseStatus::DecodeError},
                         });
    return id;
  }

  auto response = target->submit(id, transaction);
  if (response.has_value()) {
    trace_transaction(transaction, *response);
  }
  pending_.emplace(
      id, PendingTransaction{target, transaction, std::move(response)});
  return id;
}

auto DeviceManager::poll(transaction_id_t transaction) noexcept
    -> std::optional<Response> {
  auto found = pending_.find(transaction);
  if (found == pending_.end()) {
    return std::nullopt;
  }

  auto &pending = found->second;
  if (!pending.response.has_value() && pending.target != nullptr) {
    pending.response = pending.target->poll(transaction);
    if (pending.response.has_value()) {
      trace_transaction(pending.request, *pending.response);
    }
  }
  return pending.response;
}

auto DeviceManager::complete(transaction_id_t transaction) noexcept -> bool {
  const auto found = pending_.find(transaction);
  if (found == pending_.end()) {
    return false;
  }
  auto &pending = found->second;
  if (!pending.response.has_value()) {
    return false;
  }
  if (pending.target != nullptr) {
    pending.target->complete(transaction);
  }
  if (pending.response->event.type != DeviceEventType::None) {
    events_.push_back(pending.response->event);
  }
  pending_.erase(found);
  return true;
}

auto DeviceManager::take_event() noexcept -> std::optional<DeviceEvent> {
  if (events_.empty()) {
    return std::nullopt;
  }
  const auto event = events_.front();
  events_.pop_front();
  return event;
}

void DeviceManager::reset() noexcept {
  pending_.clear();
  events_.clear();
  next_transaction_ = 1;
  for (auto &slot : devices_) {
    slot.device->reset();
  }
}

void DeviceManager::clock_tick() noexcept {
  for (auto &slot : devices_) {
    slot.device->clock_tick();
  }
}

void DeviceManager::dump_mmio_map() const {
  HAL_INFO("--- MMIO Map Summary ---")
  for (const auto &slot : devices_) {
    if (slot.mmio == nullptr) {
      continue;
    }
    const auto first = slot.mmio->base_address();
    const auto last = first + slot.mmio->size() - 1;
    HAL_INFO("{:<12} [0x{:08X} - 0x{:08X}]", slot.device->name(), first, last)
  }
}

} // namespace demu::hal
