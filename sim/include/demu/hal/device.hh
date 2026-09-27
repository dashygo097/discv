#pragma once

#include "demu/hal/platform.hh"
#include <string>
#include <string_view>

namespace demu::hal {

class Device {
public:
  Device(std::string_view name, DeviceType type) : name_(name), type_(type) {}

  virtual ~Device() = default;

  Device(const Device &) = delete;
  auto operator=(const Device &) -> Device & = delete;
  Device(Device &&) = delete;
  auto operator=(Device &&) -> Device & = delete;

  virtual void clock_tick() = 0;
  virtual void reset() = 0;

  [[nodiscard]] auto name() const noexcept -> const char * {
    return name_.c_str();
  }
  [[nodiscard]] auto type() const noexcept -> DeviceType { return type_; }

private:
  std::string name_;
  DeviceType type_;
};

} // namespace demu::hal
