#include "demu/sim.hh"
#include "demu/decoder.hh"
#include "demu/dpi/runtime.hh"
#include "demu/logger.hh"
#include <chrono>

namespace demu {

DemuSimulator::DemuSimulator(bool enabled_trace, int threads, int argc,
                             char **argv)
    : trace_enabled_(enabled_trace) {
  context_ = std::make_unique<VerilatedContext>();
  context_->debug(0);
  context_->randReset(2);
  context_->threads(threads);
  context_->commandArgs(argc, argv);
  if (trace_enabled_) {
    context_->traceEverOn(true);
  }

  dut_ = std::make_unique<Vdemu_sim_top>(context_.get(), "TOP");
  device_manager_ = std::make_unique<hal::DeviceManager>();
  dpi::bind(*this);
}

DemuSimulator::~DemuSimulator() {
  dpi::unbind(*this);
  dut_->final();
#ifdef ENABLE_TRACE
  if (vcd_) {
    vcd_->close();
  }
#endif
}

auto DemuSimulator::load_bin(const std::string &filename) -> bool {
  return device_manager_->load_binary(filename);
}

void DemuSimulator::init() {
  DEMU_INFO("DEMU Simulator Initializing...")

  if (!device_manager_->configure()) {
    DEMU_ERROR("Failed to configure the simulated platform")
  }
  device_manager_->dump_mmio_map();

#ifdef ENABLE_TRACE
  if (trace_enabled_) {
    Verilated::mkdir("logs");
    vcd_ = std::make_unique<VerilatedVcdC>();
    dut_->trace(vcd_.get(), 99);
    vcd_->open("logs/demu_rv32_trace.vcd");
    DEMU_DEBUG("VCD tracing enabled: logs/demu_rv32_trace.vcd")
  }
#else
  if (trace_enabled_) {
    DEMU_ERROR("Tracing requested, but DEMU was built without trace support")
  }
#endif
}

void DemuSimulator::reset(std::uint64_t cycles) {
  DEMU_INFO("Resetting...")
  dut_->rst_n_i = 0;
  terminate_ = false;
  exit_code_ = 0;
  device_manager_->reset();

  for (std::uint64_t cycle = 0; cycle < cycles; ++cycle) {
    clock_tick();
  }
  dut_->rst_n_i = 1;
  dut_->eval();

  cycle_count_ = 0;
  instret_count_ = 0;
  last_retire_pc_ = 0;
  register_values_.fill(0);
  on_reset();
  DEMU_INFO("System Reset Complete. PC: 0x{:08x}",
            static_cast<addr_t>(generated::RESET_VECTOR))
}

void DemuSimulator::step(std::uint64_t cycles) {
  for (std::uint64_t cycle = 0; cycle < cycles && !is_terminate(); ++cycle) {
    clock_tick();
  }
}

void DemuSimulator::run(std::uint64_t max_cycles) {
  const std::uint64_t target = max_cycles > 0 ? max_cycles : timeout_;
  DEMU_INFO("Starting DEMU Simulation...")
  const auto start = std::chrono::high_resolution_clock::now();
  on_init();
  while (cycle_count_ < target && !is_terminate()) {
    clock_tick();
  }
  on_exit();
  const auto finish = std::chrono::high_resolution_clock::now();
  const auto elapsed =
      std::chrono::duration_cast<std::chrono::microseconds>(finish - start)
          .count();

  if (!is_terminate()) {
    exit_code_ = 1;
    DEMU_WARN("Simulation TIME OUT after {} cycles", cycle_count_)
  }
  DEMU_INFO("Simulation completed with: ")
  DEMU_INFO("  {} cycles, {} instructions, IPC: {:.3f} after {:.3f} ms",
            cycle_count_, instret_count_, ipc(),
            static_cast<double>(elapsed) / 1000.0)
  if (elapsed > 0) {
    DEMU_INFO("  simulation speed: {:.3f} kHz",
              static_cast<double>(cycle_count_) * 1000.0 / elapsed)
  }
}

void DemuSimulator::accept_retirement(addr_t pc, instr_t instruction,
                                      std::uint8_t rd, word_t data, bool write,
                                      bool illegal) noexcept {
  ++instret_count_;
  last_retire_pc_ = pc;

  if (write && rd < NUM_ARCH_REGS) {
    register_values_[rd] = data;
    DEMU_REG_WRITE(rd, data)
  }
  if (Logger::demu_should_log(spdlog::level::debug)) {
    DEMU_DEBUG("[RETIRE] Cycle {:6d} | PC=0x{:08x} | Instr=0x{:08x} ({})",
               cycle_count_, last_retire_pc_, instruction,
               Decoder(instruction).to_string())
  }

  if (illegal) {
    exit_code_ = 1;
    terminate_ = true;
    DEMU_WARN("Illegal instruction retired at PC 0x{:08x}", last_retire_pc_)
  }
}

void DemuSimulator::clock_tick() {
  DEMU_CPU_TICK(cycle_count_)

  context_->timeInc(1);
  dut_->clk_i = 0;
  dut_->eval();
#ifdef ENABLE_TRACE
  if (vcd_) {
    vcd_->dump(context_->time());
  }
#endif

  context_->timeInc(1);
  dut_->clk_i = 1;
  dut_->eval();
  device_manager_->clock_tick();

  ++cycle_count_;
  on_clock_tick();
#ifdef ENABLE_TRACE
  if (vcd_) {
    vcd_->dump(context_->time());
  }
#endif
}

auto DemuSimulator::submit_transaction(
    hal::port_id_t port, const hal::Transaction &transaction) noexcept
    -> std::optional<hal::transaction_id_t> {
  return device_manager_->submit(port, transaction);
}

auto DemuSimulator::poll_transaction(hal::transaction_id_t transaction) noexcept
    -> std::optional<hal::Response> {
  return device_manager_->poll(transaction);
}

auto DemuSimulator::complete_transaction(
    hal::transaction_id_t transaction) noexcept -> bool {
  return device_manager_->complete(transaction);
}

void DemuSimulator::dump_registers() const {
  DEMU_INFO("Register Dump:")
  for (std::size_t index = 0; index < NUM_ARCH_REGS; index += 4) {
    DEMU_INFO(
        "  x{:02d}={:08x}  x{:02d}={:08x}  x{:02d}={:08x}  x{:02d}={:08x}",
        index, reg(index), index + 1, reg(index + 1), index + 2, reg(index + 2),
        index + 3, reg(index + 3))
  }
}

void DemuSimulator::dump_memory(addr_t start, std::size_t size) const {
  const auto *target = device_manager_->find_mmio_target(start);
  if (target == nullptr) {
    HAL_WARN("Invalid memory dump address: 0x{:08x}", start)
    return;
  }
  target->dump(start, size);
}

} // namespace demu
