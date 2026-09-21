#pragma once

#include "Vcpu_sim_top.h"
#include "demu/hal/device_manager.hh"
#include "demu/types.hh"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <memory>
#include <string>

#ifdef ENABLE_TRACE
#include "verilated_vcd_c.h"
#endif

namespace demu {

class DemuSimulator {
public:
  explicit DemuSimulator(bool enabled_trace = false, int threads = NUM_THREADS,
                         int argc = 0, char **argv = nullptr);
  virtual ~DemuSimulator();

  auto load_bin(const std::string &filename) -> bool;

  void init();
  void reset(std::uint64_t cycles = 5);
  void step(std::uint64_t cycles = 1);
  void run(std::uint64_t max_cycles = 0);
  void terminate() noexcept { terminate_ = true; }

  [[nodiscard]] auto device(addr_t addr) -> hal::Device * {
    return device_manager_->find_device_for_address(addr);
  }
  [[nodiscard]] auto pc() const noexcept -> addr_t { return last_retire_pc_; }
  [[nodiscard]] auto reg(std::uint8_t reg) const noexcept -> word_t {
    return register_values_[reg];
  }
  [[nodiscard]] auto is_terminate() const noexcept -> bool {
    return terminate_;
  }
  [[nodiscard]] auto exit_code() const noexcept -> word_t { return exit_code_; }

  void timeout(std::uint64_t timeout) noexcept { timeout_ = timeout; }

  [[nodiscard]] auto cycle_count() const noexcept -> std::uint64_t {
    return cycle_count_;
  }
  [[nodiscard]] auto instret_count() const noexcept -> std::uint64_t {
    return instret_count_;
  }
  [[nodiscard]] auto ipc() const noexcept -> double {
    return cycle_count_ == 0
               ? 0.0
               : static_cast<double>(instret_count_) / cycle_count_;
  }

  void dump_registers() const;
  void dump_memory(addr_t start, std::size_t size) const;

protected:
  std::unique_ptr<VerilatedContext> context_;
  std::unique_ptr<Vcpu_sim_top> dut_;
  std::unique_ptr<hal::DeviceManager> device_manager_;

#ifdef ENABLE_TRACE
  std::unique_ptr<VerilatedVcdC> vcd_;
#endif

  virtual void on_clock_tick() {}
  virtual void on_init() {}
  virtual void on_exit() {}
  virtual void on_reset() {}

private:
  void clock_tick();
  void handle_retirement();

  std::uint64_t timeout_{1000000};
  std::uint64_t cycle_count_{0};
  std::uint64_t instret_count_{0};
  bool trace_enabled_{false};
  bool terminate_{false};
  word_t exit_code_{0};
  addr_t last_retire_pc_{0};
  std::array<word_t, NUM_ARCH_REGS> register_values_{};
};

} // namespace demu
