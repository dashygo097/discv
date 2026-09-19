# Synthesis stage
SYNTH_BUILD_DIR := $(BUILD_DIR)/synth

SYNTH_TOOLS ?=
SYNTH_TOOL_STAMPS := $(addsuffix /.done,$(addprefix $(SYNTH_BUILD_DIR)/,$(SYNTH_TOOLS)))

.PHONY: synth synth-clean

synth: config
	@if test -z "$(strip $(SYNTH_TOOLS))"; then \
		echo "ERROR: no synthesis tool configured; add [flow.synth.<tool>] to Project.toml" >&2; \
		exit 2; \
	fi
	+@$(MAKE) --no-print-directory --keep-going $(SYNTH_TOOL_STAMPS)

$(SYNTH_BUILD_DIR)/%/.done: $(RTL_TCL) $(CONSTRAINTS_SDC) \
		$(SYNTH_DC_CONFIG) $(PROJECT_ENV) $(CONFIG_MANIFEST) \
		$(wildcard $(RTL_SOURCES)) \
		$(wildcard $(RTL_HEADERS)) \
		$(wildcard $(SCRIPT_DIR)/synth/*) $(SCRIPT_DIR)/common/check_env.sh \
		$(SCRIPT_DIR)/common/stage.sh $(SCRIPT_DIR)/common/write_run_manifest.py
	@echo "[SYNTH::$*] Running RTL synthesis"
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_ENV=$(PROJECT_ENV) \
	CONFIG_MANIFEST=$(CONFIG_MANIFEST) \
	RTL_FILELIST=$(RTL_FILELIST) \
	RTL_TCL=$(RTL_TCL) \
	CONSTRAINTS_SDC=$(CONSTRAINTS_SDC) \
	SYNTH_DC_CONFIG=$(SYNTH_DC_CONFIG) \
	SYNTH_TOOL=$* \
	STAGE_NAME=synth \
	STAGE_BUILD_DIR=$(SYNTH_BUILD_DIR)/$* \
	PYTHON=$(VENV_PYTHON) \
	$(SCRIPT_DIR)/synth/run.sh
	@test -f "$@"

synth-clean:
	@echo "[CLEAN] synth"
	@$(RM) $(SYNTH_BUILD_DIR)
