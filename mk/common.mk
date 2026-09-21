# Project root
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

# Directory layout
BUILD_DIR       := $(PROJECT_ROOT)/build
GENERATED_DIR   := $(BUILD_DIR)/generated
RTL_DIR         := $(PROJECT_ROOT)/rtl
CONFIG_DIR      := $(PROJECT_ROOT)/config
CONSTRAINT_DIR  := $(PROJECT_ROOT)/constraints
SCRIPT_DIR      := $(PROJECT_ROOT)/scripts

# Generated from Project.toml
RTL_FILELIST := $(GENERATED_DIR)/rtl.f
RTL_TCL := $(GENERATED_DIR)/rtl.tcl
CONSTRAINTS_SDC := $(GENERATED_DIR)/constraints.sdc
SYNTH_DC_CONFIG := $(GENERATED_DIR)/synth.dc.tcl
SIM_CONFIG_CMAKE := $(GENERATED_DIR)/sim.cmake
SIM_CONFIG_HEADER := $(GENERATED_DIR)/demu/generated/cfg.hh
SIM_DEVICES_HEADER := $(GENERATED_DIR)/demu/generated/devices.hh

# Common utilities
MKDIR := mkdir -p
RM    := rm -rf

# Common targets
.PHONY: dirs init clean distclean help

dirs:
	@$(MKDIR) $(BUILD_DIR)

init: dirs
	@echo "[INIT] Initializing Project"
	@test ! -e $(PROJECT_ROOT)/Project.toml || { \
		echo "ERROR: $(PROJECT_ROOT)/Project.toml already exists" >&2; \
		exit 1; \
	}
	@cp $(PROJECT_ROOT)/.project.template.toml $(PROJECT_ROOT)/Project.toml
	@echo "[INIT] $(PROJECT_ROOT)/Project.toml"

clean:
	@$(MAKE) --no-print-directory config-clean lint-clean synth-clean sim-clean
	@echo "[CLEAN] Generated flow outputs removed; virtual environment preserved"

distclean:
	@test "$(BUILD_DIR)" = "$(PROJECT_ROOT)/build"
	@test "$(PROJECT_CONFIG)" = "$(PROJECT_ROOT)/Project.toml"
	@echo "[DISTCLEAN] $(BUILD_DIR)"
	@$(RM) "$(BUILD_DIR)"
	@echo "[DISTCLEAN] $(PROJECT_CONFIG)"
	@rm -f "$(PROJECT_CONFIG)"

help:
	@echo "Available targets:"
	@echo "  init         Init project"
	@echo "  env          Create or update the project Python environment"
	@echo "  config       Validate Project.toml and generate build configuration"
	@echo "  lint         Run RTL lint"
	@echo "  synth        Run RTL synthesis"
	@echo "  sim          Build the configured RTL simulator"
	@echo "  sim-build    Alias for sim"
	@echo "  sim-run      Run the simulator with PROGRAM=path/to/program.bin"
	@echo "  workflow     Run the ordered stages from Project.toml"
	@echo "  clean        Remove generated flow outputs"
	@echo "  distclean    Remove build directory and Project.toml"
