#pragma once

#include "demu/hal/device.hh"
#include <optional>

namespace demu::hal::host_exit {

class HostExit final : public Device {
public:
  explicit HostExit(const DeviceDescriptor &desc) : Device(desc) {}

  void clock_tick() override {}
  void reset() override { exit_code_.reset(); }

  [[nodiscard]] auto access(addr_t address, bool write, word_t data,
                            byte_t strb) noexcept
      -> DeviceAccessResult override {
    if (!write || address != base_address() || strb != byte_t{0x0F}) {
      return DeviceAccessResult{0, true};
    }
    exit_code_ = data;
    return DeviceAccessResult{0, false};
  }

  [[nodiscard]] auto take_exit_code() noexcept
      -> std::optional<word_t> override {
    auto exit_code = exit_code_;
    exit_code_.reset();
    return exit_code;
  }

private:
  std::optional<word_t> exit_code_;
};

} // namespace demu::hal::host_exit
