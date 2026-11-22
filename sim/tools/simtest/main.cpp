#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <demu.hh>
#include <iostream>
#include <string>
#include <string_view>

namespace {

void print_usage(const char *program) {
  std::cout << "Usage: " << program << " [options] <program.bin>\n"
            << "  -c, --cycles <n>        Cycle limit (default 1000000)\n"
            << "  -r, --reset-cycles <n>  Reset cycles (default 5)\n"
            << "  -h, --help              Show this help message\n";
}

} // namespace

auto main(int argc, char **argv) -> int {
  std::uint64_t max_cycles = 1000000;
  std::uint64_t reset_cycles = 5;
  std::string program_file;

  for (int i = 1; i < argc; ++i) {
    const std::string_view arg = argv[i];
    if (arg == "-h" || arg == "--help") {
      print_usage(argv[0]);
      return EXIT_SUCCESS;
    }
    if (arg.empty() || arg.front() == '+') {
      continue;
    }
    if (arg.front() != '-' && program_file.empty()) {
      program_file = arg;
      continue;
    }

    const std::size_t separator = arg.find('=');
    const std::string_view option = arg.substr(0, separator);
    const bool cycles = option == "-c" || option == "--cycles";
    if (!cycles && option != "-r" && option != "--reset-cycles") {
      std::cerr << "Unexpected argument: " << arg << '\n';
      return EXIT_FAILURE;
    }
    std::string_view value;
    if (separator != std::string_view::npos) {
      value = arg.substr(separator + 1);
    } else if (i + 1 < argc) {
      value = argv[++i];
    } else {
      std::cerr << "Missing value for " << option << '\n';
      return EXIT_FAILURE;
    }

    std::uint64_t &count = cycles ? max_cycles : reset_cycles;
    const char *end = value.data() + value.size();
    const auto result = std::from_chars(value.data(), end, count);
    if (result.ec != std::errc{} || result.ptr != end) {
      std::cerr << "Invalid value for " << option << ": " << value << '\n';
      return EXIT_FAILURE;
    }
  }

  if (program_file.empty()) {
    print_usage(argv[0]);
    return EXIT_FAILURE;
  }

  demu::Logger::init(spdlog::level::info);
  demu::DemuSimulator sim(false, NUM_THREADS, argc, argv);
  sim.init();
  sim.reset(reset_cycles);
  if (!sim.load_bin(program_file)) {
    std::cerr << "Error: Failed to load program\n";
    return EXIT_FAILURE;
  }

  sim.run(max_cycles);
  if (sim.exit_code() != 0) {
    std::cerr << "Simulation exit status: " << sim.exit_code() << '\n';
    return EXIT_FAILURE;
  }
  if (!sim.host_exit_requested()) {
    std::cerr << "Simulation stopped without host_exit\n";
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
