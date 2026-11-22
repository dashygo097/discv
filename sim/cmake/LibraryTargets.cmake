add_library(demu
  ${DEMU_SOURCES}
  ${DEMU_HEADERS}
  ${GEN_HEADERS}
)

verilate(demu
  SOURCES "${SIM_BENDER_FILELIST}"
  VERILATOR_ARGS
    ${DEMU_VERILATOR_ARGS}
    -j 0
    --top-module ${TOP_MODULE}
    -f

  PREFIX Vdemu_sim_top
  TRACE_THREADS ${NUM_TRACE_THREADS}
  THREADS ${NUM_THREADS}
)

target_include_directories(demu PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include>"
  "${GENERATED_INCLUDE_DIR}"
)

target_compile_definitions(demu PUBLIC
  NUM_THREADS=${NUM_THREADS}
)

if(ENABLE_TRACE)
  target_compile_definitions(demu PUBLIC ENABLE_TRACE)
endif()

target_link_libraries(demu PUBLIC
  spdlog::spdlog
  Threads::Threads
)

set_target_properties(demu PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)
