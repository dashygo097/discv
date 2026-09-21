#pragma once

#include "demu/hal/device.hh"
#include "demu/hal/port_handler.hh"
#include <functional>
#include <utility>
#include <verilated.h>

namespace demu::hal::virt {

struct PortSignals {
  CData *req_valid;
  CData *req_ready;
  IData *req_address;
  CData *req_write;
  IData *req_data;
  CData *req_strb;
  CData *rsp_valid;
  CData *rsp_ready;
  IData *rsp_data;
  CData *rsp_error;

  [[nodiscard]] auto valid() const noexcept -> bool {
    return req_valid != nullptr && req_ready != nullptr &&
           req_address != nullptr && rsp_valid != nullptr &&
           rsp_ready != nullptr && rsp_data != nullptr &&
           rsp_error != nullptr;
  }
};

class PortHandler final : public hal::PortHandler {
public:
  using Access =
      std::function<DeviceAccessResult(addr_t, bool, word_t, byte_t)>;
  using ResponseComplete = std::function<void()>;

  PortHandler(PortSignals signals, Access access,
              ResponseComplete response_complete = {})
      : signals_(signals), access_(std::move(access)),
        response_complete_(std::move(response_complete)) {}

  void handle() noexcept override;
  void reset() noexcept override;

  [[nodiscard]] auto protocol_name() const noexcept -> const char * override {
    return "virtual raw-port bus";
  }

private:
  struct Response {
    word_t data{0};
    bool error{false};
    bool valid{false};
  };

  PortSignals signals_;
  Access access_;
  ResponseComplete response_complete_;
  Response response_;
};

} // namespace demu::hal::virt
