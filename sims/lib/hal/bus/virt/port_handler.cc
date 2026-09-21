#include "demu/hal/bus/virt/port_handler.hh"
#include "demu/logger.hh"

namespace demu::hal::virt {

void PortHandler::handle() noexcept {
  if (!signals_.valid() || !access_) {
    HAL_WARN("Ignoring an invalid virtual-bus port binding")
    return;
  }

  const bool response_fire = response_.valid && *signals_.rsp_ready;
  const bool allow_request = !response_.valid || *signals_.rsp_ready;
  const bool request_fire = *signals_.req_valid && allow_request;

  *signals_.req_ready = allow_request;
  *signals_.rsp_valid = response_.valid;
  *signals_.rsp_data = response_.data;
  *signals_.rsp_error = response_.error;

  if (response_fire) {
    response_ = {};
    if (response_complete_) {
      response_complete_();
    }
  }

  if (request_fire) {
    const bool write =
        signals_.req_write != nullptr && *signals_.req_write != 0;
    const word_t data = signals_.req_data == nullptr ? 0 : *signals_.req_data;
    const byte_t strb = signals_.req_strb == nullptr ? 0 : *signals_.req_strb;
    const auto result = access_(*signals_.req_address, write, data, strb);
    response_ = Response{result.data, result.error, true};
  }
}

void PortHandler::reset() noexcept {
  response_ = {};
  if (!signals_.valid()) {
    return;
  }
  *signals_.req_ready = 1;
  *signals_.rsp_valid = 0;
  *signals_.rsp_data = 0;
  *signals_.rsp_error = 0;
}

} // namespace demu::hal::virt
