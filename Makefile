PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BUILD_DIR := $(PROJECT_ROOT)/build
VENV_PYTHON := $(BUILD_DIR)/.venv/bin/python
BOOTSTRAP_PYTHON ?= python3
.DEFAULT_GOAL := help

.PHONY: help env init config deps-update lint synth formal sim sim-build sim-run workflow check clean distclean
export PROGRAM SIM_ARGS
export PROJECT_MAKE := $(MAKE)

env:
	@PYTHON_BIN="$(BOOTSTRAP_PYTHON)" PROJECT_VENV_DIR="$(BUILD_DIR)/.venv" \
		"$(PROJECT_ROOT)/scripts/config/setup_venv.sh"

config deps-update lint synth formal sim sim-build sim-run workflow check: env
	+@"$(VENV_PYTHON)" "$(PROJECT_ROOT)/scripts/config/flow.py" $@

init:
	@test ! -e "$(PROJECT_ROOT)/Project.toml" || { echo "ERROR: Project.toml already exists" >&2; exit 1; }
	@cp "$(PROJECT_ROOT)/.project.template.toml" "$(PROJECT_ROOT)/Project.toml"

clean:
	@rm -rf "$(BUILD_DIR)/generated" "$(BUILD_DIR)/lint" "$(BUILD_DIR)/synth" \
		"$(BUILD_DIR)/formal" "$(BUILD_DIR)/sim"
	@rm -f "$(PROJECT_ROOT)/Bender.yml"
	@echo "[CLEAN] Flow outputs removed; environment and package lock preserved"

distclean: clean
	@test "$(BUILD_DIR)" = "$(PROJECT_ROOT)/build"
	@rm -rf "$(BUILD_DIR)"
	@rm -f "$(PROJECT_ROOT)/Project.toml"
	@echo "[DISTCLEAN] build/ and Project.toml removed; Bender.lock preserved"

help:
	@echo "Edit Project.toml; run make <target>:"
	@echo "  init          Create Project.toml from the template"
	@echo "  env           Prepare the Python environment"
	@echo "  config        Generate configuration and locked Bender tool inputs"
	@echo "  deps-update   Explicitly resolve/update Bender.lock"
	@echo "  lint          Run all configured linters/technologies"
	@echo "  synth         Run all configured synthesis backends/technologies"
	@echo "  formal        Compare RTL with the final synthesized gate netlist"
	@echo "  sim           Build DEMU (sim-build is an alias)"
	@echo "  sim-run       Build and run: PROGRAM=program.bin SIM_ARGS='-L3'"
	@echo "  workflow      Run Project.toml workflow stages in order"
	@echo "  check         Verify Bender integration and incremental build contracts"
	@echo "  clean         Remove flow outputs, keeping environment/dependencies"
	@echo "  distclean     Remove build/ and Project.toml, keeping dependency lock"
