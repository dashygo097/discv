#pragma once

#include <cstdint>
#include <string_view>

namespace demu::hal {

using port_id_t = std::uint32_t;
using device_id_t = std::uint32_t;
using transaction_id_t = std::uint64_t;

enum class DeviceType {
  TCM,
  Console,
  HostExit,
};

struct PortDescriptor {
  std::string_view name;
};

struct DeviceDescriptor {
  std::string_view name;
  DeviceType type;
  std::uint64_t base;
  std::uint64_t size;
  bool load;
  std::uint64_t load_address;
};

} // namespace demu::hal
