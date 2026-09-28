# Synthesis stage
SYNTH_BUILD_DIR := $(BUILD_DIR)/synth

SYNTH_TOOLS ?=
SYNTH_TOOL_STAMPS := $(addsuffix /.done,$(addprefix $(SYNTH_BUILD_DIR)/,$(SYNTH_TOOLS)))

SYNTH_COMMON_DEPS := $(RTL_TCL) $(ARCH_PACKAGE) $(CONSTRAINTS_SDC) \
		$(PROJECT_ENV) $(CONFIG_MANIFEST) \
		$(wildcard $(RTL_SOURCES)) \
		$(wildcard $(RTL_HEADERS)) \
		$(wildcard $(SCRIPT_DIR)/synth/*) $(SCRIPT_DIR)/common/check_env.sh \
		$(SCRIPT_DIR)/common/stage.sh $(SCRIPT_DIR)/common/write_run_manifest.py

.PHONY: synth synth-run synth-clean

synth: config
	+@$(MAKE) --no-print-directory --keep-going synth-run

synth-run: $(SYNTH_TOOL_STAMPS)
	@if test -z "$(strip $(SYNTH_TOOLS))"; then \
		echo "ERROR: no synthesis tool configured; add [flow.synth.<tool>] to Project.toml" >&2; \
		exit 2; \
	fi

$(SYNTH_BUILD_DIR)/dc/.done: SYNTH_TOOL_CONFIG := $(SYNTH_DC_CONFIG)
$(SYNTH_BUILD_DIR)/dc/.done: $(SYNTH_DC_CONFIG)

$(SYNTH_BUILD_DIR)/%/.done: $(SYNTH_COMMON_DEPS)
	@echo "[SYNTH::$*] Running RTL synthesis"
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_ENV=$(PROJECT_ENV) \
	CONFIG_MANIFEST=$(CONFIG_MANIFEST) \
	RTL_TCL=$(RTL_TCL) \
	CONSTRAINTS_SDC=$(CONSTRAINTS_SDC) \
	SYNTH_TOOL_CONFIG=$(SYNTH_TOOL_CONFIG) \
	SYNTH_TOOL=$* \
	STAGE_NAME=synth \
	STAGE_BUILD_DIR=$(SYNTH_BUILD_DIR)/$* \
	PYTHON=$(VENV_PYTHON) \
	$(SCRIPT_DIR)/synth/run.sh
	@test -f "$@"

synth-clean:
	@echo "[CLEAN] synth"
	@$(RM) $(SYNTH_BUILD_DIR)
