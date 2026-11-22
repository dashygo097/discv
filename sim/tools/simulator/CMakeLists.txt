add_executable("${SIM_EXECUTABLE}" main.cpp)
target_link_libraries("${SIM_EXECUTABLE}" PRIVATE demu)
set_target_properties("${SIM_EXECUTABLE}" PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
install(TARGETS "${SIM_EXECUTABLE}" DESTINATION bin)
