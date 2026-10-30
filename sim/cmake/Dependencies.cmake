find_package(Threads REQUIRED)
if(SIM_SPDLOG_VERSION)
  find_package(spdlog ${SIM_SPDLOG_VERSION} EXACT CONFIG REQUIRED)
else()
  find_package(spdlog CONFIG REQUIRED)
endif()
find_package(verilator REQUIRED)

if(NOT verilator_FOUND)
  message(FATAL_ERROR "Verilator not found. Install Verilator or set VERILATOR_ROOT.")
endif()

if(NOT EXISTS "${SIM_BENDER_FILELIST}")
  message(FATAL_ERROR "Bender Verilator input file is missing")
endif()
if(NOT SIM_RTL_TOP)
  message(FATAL_ERROR "SIM_RTL_TOP is empty in generated sim.cmake")
endif()

set(DEMU_VERILATOR_ARGS
  -Wall
  -Wno-WIDTH
  -Wno-UNUSED
  -Wno-UNOPTFLAT
  -Wno-DECLFILENAME
  -Wno-PINCONNECTEMPTY
  -Wno-COVERIGN
  "-DDEMU_RTL_TOP=${SIM_RTL_TOP}"
  ${SIM_VERILATOR_OPTIONS}
)

if(ENABLE_TRACE)
  list(APPEND DEMU_VERILATOR_ARGS --trace)
endif()
