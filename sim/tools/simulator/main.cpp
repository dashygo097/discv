#include <charconv>
#include <cstdlib>
#include <cstring>
#include <demu.hh>
#include <iostream>
#include <string>
#include <string_view>

class DemuSimulatorTop final : public demu::DemuSimulator {
public:
  explicit DemuSimulatorTop(bool enabled_trace = false,
                            int threads = NUM_THREADS, int argc = 0,
                            char **argv = nullptr)
      : DemuSimulator(enabled_trace, threads, argc, argv) {}

protected:
  void on_init() override {}
  void on_clock_tick() override {}
  void on_exit() override {}
  void on_reset() override {}

private:
};

void print_usage(const char *prog) {
  std::cout << "Usage: " << prog << " [options] <program_file>\n\n";
  std::cout << "Options:\n";
  std::cout << "  -h, --help                    Show this help message\n";
  std::cout << "  -t, --trace                   Enable VCD trace\n";
  std::cout << "  -T, --threads <n>             Number of Verilator threads "
               "(default: NUM_THREADS)\n";
  std::cout << "  -c, --cycles <n>              Run up to n cycles\n";
  std::cout << "  -r, --reset-cycles <n>        Hold reset for n cycles\n";
  std::cout
      << "  -d, --dump-regs               Dump registers after execution\n";
  std::cout << "  -m, --dump-mem <addr> <size>  Dump memory region\n";
  std::cout << "  -L12345,                      Set log level (5=error, "
               "4=warn, 3=info, 2=debug, 1=trace)\n";
  std::cout << "  +<arg>                        Native Verilator arguments "
               "(e.g., +verilator+rand+reset+2)\n";
  std::cout << "\nProgram format: raw binary\n";
  std::cout << std::endl;
}

auto main(int argc, char **argv) -> int {
  std::cout << R"(________  _______   _____ ______   ___  ___     
|\   ___ \|\  ___ \ |\   _ \  _   \|\  \|\  \    
\ \  \_|\ \ \   __/|\ \  \\\__\ \  \ \  \\\  \   
 \ \  \ \\ \ \  \_|/_\ \  \\|__| \  \ \  \\\  \  
  \ \  \_\\ \ \  \_|\ \ \  \    \ \  \ \  \\\  \ 
   \ \_______\ \_______\ \__\    \ \__\ \_______\
    \|_______|\|_______|\|__|     \|__|\|_______|
                                                 
                                                 )"
            << "\n";

  if (argc < 2) {
    print_usage(argv[0]);
    return 1;
  }

  std::string program_file;
  bool enable_trace = false;
  bool dump_regs = false;
  int threads = NUM_THREADS;
  uint64_t max_cycles = 0;
  uint64_t reset_cycles = 5;
  uint32_t dump_mem_addr = 0;
  uint32_t dump_mem_size = 0;
  bool dump_mem = false;
  spdlog::level::level_enum spdlog_level = spdlog::level::info;

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];

    if (arg == "-h" || arg == "--help") {
      print_usage(argv[0]);
      return 0;
    } else if (arg == "-t" || arg == "--trace") {
      enable_trace = true;
    } else if (arg == "-T" || arg == "--threads") {
      if (i + 1 < argc) {
        threads = std::stoi(argv[++i]);
      }
    } else if (arg == "-d" || arg == "--dump-regs") {
      dump_regs = true;
    } else if (arg == "-c" || arg == "--cycles" || arg.rfind("-c=", 0) == 0 ||
               arg.rfind("--cycles=", 0) == 0) {
      const std::size_t separator = arg.find('=');
      std::string_view value;
      if (separator != std::string::npos) {
        value = std::string_view(arg).substr(separator + 1);
      } else if (i + 1 < argc) {
        value = argv[++i];
      } else {
        std::cerr << "Missing cycle count\n";
        return EXIT_FAILURE;
      }
      const char *end = value.data() + value.size();
      const auto result = std::from_chars(value.data(), end, max_cycles);
      if (result.ec != std::errc{} || result.ptr != end) {
        std::cerr << "Invalid cycle count: " << value << '\n';
        return EXIT_FAILURE;
      }
    } else if (arg == "-r" || arg == "--reset-cycles") {
      if (i + 1 < argc) {
        reset_cycles = std::stoull(argv[++i]);
      }
    } else if (arg == "-m" || arg == "--dump-mem") {
      if (i + 2 < argc) {
        dump_mem_addr = std::stoul(argv[++i], nullptr, 16);
        dump_mem_size = std::stoul(argv[++i], nullptr, 16);
        dump_mem = true;
      }
    } else if (arg[0] == '-' && arg.length() > 1 && arg[1] == 'L') {
      int log_level = std::stoi(arg.substr(2));
      switch (log_level) {
      case 1:
        spdlog_level = spdlog::level::trace;
        break;
      case 2:
        spdlog_level = spdlog::level::debug;
        break;
      case 3:
        spdlog_level = spdlog::level::info;
        break;
      case 4:
        spdlog_level = spdlog::level::warn;
        break;
      case 5:
        spdlog_level = spdlog::level::err;
        break;
      default:
        std::cerr << "Unknown log level: " << log_level << std::endl;
      }
    } else if (arg[0] == '+') {
      continue;
    } else if (arg[0] != '-') {
      program_file = arg;
    } else {
      std::cerr << "Unknown option: " << arg << std::endl;
      return 1;
    }
  }

  if (program_file.empty()) {
    std::cerr << "Error: No program file specified\n";
    print_usage(argv[0]);
    return 1;
  }

  demu::Logger::init(spdlog_level);

  DemuSimulatorTop sim(enable_trace, threads, argc, argv);

  sim.init();
  sim.reset(reset_cycles);

  if (!sim.load_bin(program_file)) {
    std::cerr << "Error: Failed to load program\n";
    return 1;
  }

  sim.run(max_cycles);

  if (dump_regs) {
    sim.dump_registers();
  }

  if (dump_mem) {
    sim.dump_memory(dump_mem_addr, dump_mem_size);
  }

  if (sim.exit_code() != 0) {
    std::cerr << "Simulation exit status: " << sim.exit_code() << '\n';
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
