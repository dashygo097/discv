# Lint stage
LINT_BUILD_DIR := $(BUILD_DIR)/lint

# Inputs
LINT_FILELIST := $(RTL_FILELIST)
RTL_SOURCES ?=
RTL_HEADERS ?=

LINT_STAMP := $(LINT_BUILD_DIR)/.done

# Targets
.PHONY: lint lint-clean

lint: $(LINT_STAMP)

$(LINT_STAMP): $(LINT_FILELIST) $(PROJECT_ENV) $(CONFIG_MANIFEST) \
		$(wildcard $(RTL_SOURCES)) \
		$(wildcard $(RTL_HEADERS)) \
		$(wildcard $(SCRIPT_DIR)/lint/*) $(SCRIPT_DIR)/common/check_env.sh \
		$(SCRIPT_DIR)/common/stage.sh $(SCRIPT_DIR)/common/write_run_manifest.py
	@echo "[LINT] Running RTL lint"
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_ENV=$(PROJECT_ENV) \
	CONFIG_MANIFEST=$(CONFIG_MANIFEST) \
	RTL_FILELIST=$(LINT_FILELIST) \
	STAGE_NAME=lint \
	STAGE_BUILD_DIR=$(LINT_BUILD_DIR) \
	PYTHON=$(VENV_PYTHON) \
	$(SCRIPT_DIR)/lint/run.sh
	@test -f "$@"

lint-clean:
	@echo "[CLEAN] lint"
	@$(RM) $(LINT_BUILD_DIR)
