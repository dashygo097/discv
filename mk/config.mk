# Project configuration
PROJECT_CONFIG        := $(PROJECT_ROOT)/Project.toml
PROJECT_CONFIG_SCRIPT := $(SCRIPT_DIR)/config/project_config.py
PROJECT_CONFIG_RUNNER := $(SCRIPT_DIR)/config/run.sh
CONFIG_MANIFEST       := $(GENERATED_DIR)/manifest.json
CONFIG_MAKEFILE       := $(GENERATED_DIR)/project.mk
CONFIG_SVH            := $(GENERATED_DIR)/cfg.svh
PROJECT_ENV           := $(GENERATED_DIR)/project.env
CONFIG_OUTPUTS        := $(RTL_FILELIST) $(CONFIG_MAKEFILE) $(CONFIG_SVH) \
		$(PROJECT_ENV) $(CONFIG_MANIFEST)
CONFIG_STAMP          := $(GENERATED_DIR)/.done
PYTHON                ?= $(VENV_PYTHON)

# Once generated, this list makes additions and removals below an RTL root
# invalidate configuration without requiring a Project.toml edit.
ifneq ($(filter config lint workflow,$(MAKECMDGOALS)),)
-include $(CONFIG_MAKEFILE)
endif
RTL_DISCOVERY_DIRS ?=
CONFIG_RELOCATION_PREREQUISITE :=

# Generated tool inputs may contain absolute paths. Regenerate them after a
# checkout is moved, and discard stale discovery paths before Make uses them.
ifneq ($(GENERATED_PROJECT_ROOT),$(PROJECT_ROOT))
RTL_DISCOVERY_DIRS :=
CONFIG_RELOCATION_PREREQUISITE := config-relocated
.PHONY: config-relocated
config-relocated:
endif

.PHONY: config config-clean

config: $(CONFIG_OUTPUTS)

$(CONFIG_STAMP): $(CONFIG_RELOCATION_PREREQUISITE) $(VENV_STAMP) $(PROJECT_CONFIG) \
		$(PROJECT_CONFIG_SCRIPT) $(PROJECT_CONFIG_RUNNER) \
		$(RTL_DISCOVERY_DIRS) \
		$(SCRIPT_DIR)/common/check_env.sh
	@echo "[CONFIG] Generating project configuration"
	@$(MKDIR) $(GENERATED_DIR)
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_CONFIG=$(PROJECT_CONFIG) \
	PROJECT_CONFIG_SCRIPT=$(PROJECT_CONFIG_SCRIPT) \
	GENERATED_DIR=$(GENERATED_DIR) \
	PYTHON=$(PYTHON) \
	$(PROJECT_CONFIG_RUNNER)
	@touch $@

$(CONFIG_OUTPUTS): $(CONFIG_STAMP)
	@if ! test -f $@; then \
		echo "[CONFIG] Regenerating missing output: $@"; \
		PROJECT_ROOT=$(PROJECT_ROOT) \
		PROJECT_CONFIG=$(PROJECT_CONFIG) \
		PROJECT_CONFIG_SCRIPT=$(PROJECT_CONFIG_SCRIPT) \
		GENERATED_DIR=$(GENERATED_DIR) \
		PYTHON=$(PYTHON) \
		$(PROJECT_CONFIG_RUNNER); \
		touch $(CONFIG_STAMP); \
	fi

config-clean:
	@echo "[CLEAN] config"
	@$(RM) $(GENERATED_DIR)
