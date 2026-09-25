#pragma once

#include "demu/hal/platform.hh"
#include "demu/types.hh"
#include <cstdint>
#include <optional>

namespace demu::hal {

enum class AccessType : std::uint8_t {
  Read,
  Write,
};

enum class ResponseStatus : std::uint8_t {
  Okay,
  DecodeError,
  SlaveError,
  Misaligned,
  Unsupported,
};

enum class DeviceEventType : std::uint8_t {
  None,
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

class MmioTarget {
public:
  virtual ~MmioTarget() = default;

  [[nodiscard]] virtual auto submit(transaction_id_t id,
                                    const Transaction &transaction) noexcept
      -> std::optional<Response> = 0;

  [[nodiscard]] virtual auto poll(transaction_id_t) noexcept
      -> std::optional<Response> {
    return std::nullopt;
  }

  virtual void complete(transaction_id_t) noexcept {}
};

} // namespace demu::hal
