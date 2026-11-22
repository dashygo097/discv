#pragma once

#include "demu/types.hh"
#include <cstdint>

namespace demu::hal {

enum class AccessType : std::uint8_t {
  Read,
  Write,
};

enum class ResponseStatus : std::uint8_t {
  Okay = 0,
  DecodeError = 1,
  SlaveError = 2,
  Misaligned = 3,
  Unsupported = 4,
};

enum class DeviceEventType : std::uint8_t {
  None,
  ConsoleWrite,
  Exit,
};

struct Transaction {
  addr_t address{0};
  AccessType access{AccessType::Read};
  std::uint8_t size{sizeof(word_t)};
  word_t data{0};
  byte_t strobe{0};
};

struct DeviceEvent {
  DeviceEventType type{DeviceEventType::None};
  word_t value{0};
};

struct Response {
  ResponseStatus status{ResponseStatus::Okay};
  word_t data{0};
  DeviceEvent event{};

  [[nodiscard]] auto error() const noexcept -> bool {
    return status != ResponseStatus::Okay;
  }
};

} // namespace demu::hal
