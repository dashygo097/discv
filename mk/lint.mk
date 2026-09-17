# Lint directories
LINT_BUILD_DIR  := $(BUILD_DIR)/lint
LINT_LOG_DIR    := $(LINT_BUILD_DIR)/logs
LINT_REPORT_DIR := $(LINT_BUILD_DIR)/reports
LINT_WORK_DIR   := $(LINT_BUILD_DIR)/work

# Inputs
LINT_FILELIST := $(RTL_FILELIST)
ifneq ($(filter lint,$(MAKECMDGOALS)),)
ifneq ($(wildcard $(CONFIG_MAKEFILE)),)
include $(CONFIG_MAKEFILE)
endif
endif
RTL_SOURCES ?=
RTL_HEADERS ?=

# Outputs
LINT_LOG    := $(LINT_LOG_DIR)/lint.log
LINT_REPORT := $(LINT_REPORT_DIR)/lint.rpt
LINT_STAMP  := $(LINT_BUILD_DIR)/.done

# Targets
.PHONY: lint lint-clean

lint: $(LINT_STAMP)

$(LINT_STAMP): $(LINT_FILELIST) $(PROJECT_ENV) $(RTL_SOURCES) $(RTL_HEADERS) \
		$(SCRIPT_DIR)/lint/run.sh $(SCRIPT_DIR)/common/check_env.sh
	@echo "[LINT] Running RTL lint"
	@$(MKDIR) $(LINT_LOG_DIR)
	@$(MKDIR) $(LINT_REPORT_DIR)
	@$(MKDIR) $(LINT_WORK_DIR)

	@PROJECT_ROOT=$(PROJECT_ROOT) \
	FILELIST=$(LINT_FILELIST) \
	PROJECT_ENV=$(PROJECT_ENV) \
	BUILD_DIR=$(LINT_BUILD_DIR) \
	$(SCRIPT_DIR)/lint/run.sh

	@touch $@

lint-clean:
	@echo "[CLEAN] lint"
	@$(RM) $(LINT_BUILD_DIR)
