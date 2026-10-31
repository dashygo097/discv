PROJECT_ROOT := $(CURDIR)
BUILD_DIR := $(PROJECT_ROOT)/build
VENV_PYTHON := $(BUILD_DIR)/.venv/bin/python
BOOTSTRAP_PYTHON ?= python3
.DEFAULT_GOAL := help

.PHONY: help env init clean distclean $(MAKECMDGOALS)
export PROGRAM SIM_ARGS
export PROJECT_MAKE := $(MAKE)
export PROJECT_ROOT
FLOW_GOALS := $(filter-out help env init clean distclean,$(MAKECMDGOALS))

env:
	@PYTHON_BIN="$(BOOTSTRAP_PYTHON)" PROJECT_VENV_DIR="$(BUILD_DIR)/.venv" \
		"$(PROJECT_ROOT)/scripts/config/setup_venv.sh"

ifneq ($(strip $(FLOW_GOALS)),)
$(FLOW_GOALS): env
	+@"$(VENV_PYTHON)" "$(PROJECT_ROOT)/scripts/config/bootstrap.py" $@
endif

init:
	@test ! -e "$(PROJECT_ROOT)/Project.toml" || { echo "ERROR: Project.toml already exists" >&2; exit 1; }
	@cp "$(PROJECT_ROOT)/.project.template.toml" "$(PROJECT_ROOT)/Project.toml"

clean:
	@for directory in "$(BUILD_DIR)"/*; do \
		if test -f "$$directory/.flow-stage"; then rm -rf "$$directory"; fi; \
	done
	@rm -rf "$(BUILD_DIR)/generated"
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
	@echo "  deps-update   Explicitly resolve/update locked dependencies"
	@echo "  lint          Run all configured linters/technologies"
	@echo "  synth         Run all configured synthesis backends/technologies"
	@echo "  formal        Compare RTL with the final synthesized gate netlist"
	@echo "  <stage>       Run the backends declared in flow.<stage>"
	@echo "  sim-run       Build and run: PROGRAM=program.bin SIM_ARGS='-L3'"
	@echo "  workflow      Run Project.toml workflow stages in order"
	@echo "  clean         Remove flow outputs, keeping environment/dependencies"
	@echo "  distclean     Remove build/ and Project.toml, keeping dependency lock"
