add_subdirectory(simulator)

# Configuration 
print_info("Configuration: \n" "92" "0")
print_info("  ISA: RISC-V RV32\n" "92" "1")
print_info("  Build Type: ${CMAKE_BUILD_TYPE}\n" "92" "1")
print_info("  C++ Compiler: ${CMAKE_CXX_COMPILER}\n" "92" "1")
print_info("  Verilator: ${VERILATOR_ROOT}\n" "92" "1")
print_info("  RTL Top: ${TOP_MODULE}\n" "92" "1")
print_info("  Enable Trace: ${ENABLE_TRACE}\n" "94" "2")
