#include "demu/dpi/runtime.hh"
#include "demu/hal/transaction.hh"
#include "demu/sim.hh"
#include "svdpi.h"
#include <cstdint>

namespace {
demu::DemuSimulator *active_simulator = nullptr;
}

namespace demu::dpi {

void bind(DemuSimulator &simulator) noexcept { active_simulator = &simulator; }

void unbind(DemuSimulator &simulator) noexcept {
  if (active_simulator == &simulator) {
    active_simulator = nullptr;
  }
}

} // namespace demu::dpi

extern "C" auto demu_context() noexcept -> void * { return active_simulator; }

extern "C" auto demu_submit(void *context, unsigned int port, svBit write,
                            unsigned int address, unsigned int data,
                            unsigned int strobe, unsigned int size,
                            unsigned long long *transaction) noexcept -> int {
  auto *simulator = static_cast<demu::DemuSimulator *>(context);
  if (simulator == nullptr || transaction == nullptr) {
    return -1;
  }

  const auto id = simulator->submit_transaction(
      port, demu::hal::Transaction{
                address,
                write != 0 ? demu::hal::AccessType::Write
                           : demu::hal::AccessType::Read,
                static_cast<std::uint8_t>(size),
                data,
                static_cast<demu::byte_t>(strobe),
            });
  if (!id.has_value()) {
    return -1;
  }
  *transaction = *id;
  return 0;
}

extern "C" auto demu_poll(void *context, unsigned long long transaction,
                          unsigned int *data, unsigned char *status) noexcept
    -> int {
  auto *simulator = static_cast<demu::DemuSimulator *>(context);
  if (simulator == nullptr || data == nullptr || status == nullptr) {
    return -1;
  }
  const auto response = simulator->poll_transaction(transaction);
  if (!response.has_value()) {
    return 0;
  }
  *data = response->data;
  *status = static_cast<unsigned char>(response->status);
  return 1;
}

extern "C" auto demu_complete(void *context,
                              unsigned long long transaction) noexcept -> int {
  auto *simulator = static_cast<demu::DemuSimulator *>(context);
  return simulator != nullptr && simulator->complete_transaction(transaction)
             ? 0
             : -1;
}

extern "C" void demu_retire(void *context, std::uint32_t pc,
                            std::uint32_t instruction, std::uint8_t rd,
                            std::uint32_t data, svBit write,
                            svBit illegal) noexcept {
  auto *simulator = static_cast<demu::DemuSimulator *>(context);
  if (simulator != nullptr) {
    simulator->accept_retirement(pc, instruction, rd, data, write != 0,
                                 illegal != 0);
  }
}
