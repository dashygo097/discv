# Simulation stage
SIM_BUILD_DIR := $(BUILD_DIR)/sim
SIM_MODEL_DIR := $(SIM_BUILD_DIR)/verilator/model
SIM_EXECUTABLE := $(SIM_MODEL_DIR)/bin/demu-riscv

SIM_TOOLS ?=
SIM_BUILD_STAMPS := $(addsuffix /model/.done,$(addprefix $(SIM_BUILD_DIR)/,$(SIM_TOOLS)))
SIM_CPP_INPUTS := $(shell find $(PROJECT_ROOT)/sims -type f 2>/dev/null)

.PHONY: sim sim-run sim-build sim-build-run sim-clean

sim: config
	+@$(MAKE) --no-print-directory sim-build-run

sim-build: config
	+@$(MAKE) --no-print-directory sim-build-run

sim-build-run: $(SIM_BUILD_STAMPS)
	@if test -z "$(strip $(SIM_TOOLS))"; then \
		echo "ERROR: no simulator configured; add [flow.sim.<tool>] to Project.toml" >&2; \
		exit 2; \
	fi

$(SIM_BUILD_DIR)/verilator/model/.done: $(SIM_EXECUTABLE)
	@printf '%s\n' "$(PROJECT_CONFIG_DIGEST)" >"$@"

$(SIM_EXECUTABLE): $(SIM_CONFIG_CMAKE) \
		$(SIM_CONFIG_HEADER) $(SIM_DEVICES_HEADER) $(PROJECT_ENV) $(CONFIG_MANIFEST) \
		$(wildcard $(RTL_SOURCES)) $(wildcard $(RTL_HEADERS)) $(SIM_CPP_INPUTS) \
		$(SCRIPT_DIR)/sim/build.sh $(SCRIPT_DIR)/common/check_env.sh
	@echo "[SIM::verilator] Building RISC-V simulator"
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_ENV=$(PROJECT_ENV) \
	SIM_CONFIG_CMAKE=$(SIM_CONFIG_CMAKE) \
	SIM_MODEL_DIR=$(SIM_MODEL_DIR) \
	$(SCRIPT_DIR)/sim/build.sh
	@test -x "$(SIM_EXECUTABLE)"

sim-run: sim-build-run
	@if test "$(SIM_TOOLS)" != "verilator"; then \
		echo "ERROR: sim currently requires exactly [flow.sim.verilator]" >&2; \
		exit 2; \
	fi
	@echo "[SIM::verilator] Running RISC-V simulator"
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_ENV=$(PROJECT_ENV) \
	CONFIG_MANIFEST=$(CONFIG_MANIFEST) \
	SIM_EXECUTABLE=$(SIM_EXECUTABLE) \
	PROGRAM="$(PROGRAM)" \
	STAGE_NAME=sim \
	STAGE_BUILD_DIR=$(SIM_BUILD_DIR)/verilator/run \
	PYTHON=$(VENV_PYTHON) \
	$(SCRIPT_DIR)/sim/run.sh

sim-clean:
	@echo "[CLEAN] sim"
	@$(RM) $(SIM_BUILD_DIR)
