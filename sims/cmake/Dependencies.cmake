find_package(Threads REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(verilator REQUIRED)

if(NOT verilator_FOUND)
  message(FATAL_ERROR "Verilator not found. Install Verilator or set VERILATOR_ROOT.")
endif()

if(NOT SIM_RTL_SOURCES)
  message(FATAL_ERROR "SIM_RTL_SOURCES is empty in generated sim.cmake")
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

foreach(INCLUDE_DIR IN LISTS SIM_RTL_INCLUDE_DIRS)
  list(APPEND DEMU_VERILATOR_ARGS "-I${INCLUDE_DIR}")
endforeach()

if(ENABLE_TRACE)
  list(APPEND DEMU_VERILATOR_ARGS --trace)
endif()
