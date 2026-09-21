#pragma once

namespace demu::hal {

class PortHandler {
public:
  virtual ~PortHandler() = default;

  virtual void handle() noexcept = 0;
  virtual void reset() noexcept = 0;

  [[nodiscard]] virtual auto protocol_name() const noexcept -> const char * = 0;
};

} // namespace demu::hal
