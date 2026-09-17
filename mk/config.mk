# Project configuration
PROJECT_CONFIG        := $(PROJECT_ROOT)/Project.toml
PROJECT_CONFIG_SCRIPT := $(SCRIPT_DIR)/config/project_config.py
PROJECT_CONFIG_RUNNER := $(SCRIPT_DIR)/config/run.sh
CONFIG_MANIFEST       := $(GENERATED_DIR)/manifest.json
CONFIG_MAKEFILE       := $(GENERATED_DIR)/project.mk
PROJECT_ENV           := $(GENERATED_DIR)/project.env
CONFIG_OUTPUTS        := $(RTL_FILELIST) $(CONFIG_MAKEFILE) $(PROJECT_ENV) $(CONFIG_MANIFEST)
CONFIG_STAMP          := $(GENERATED_DIR)/.done
VENV_PYTHON           := $(BUILD_DIR)/.venv/bin/python
PYTHON                ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)

.PHONY: config config-clean

config: $(CONFIG_OUTPUTS)

$(CONFIG_STAMP): $(PROJECT_CONFIG) $(PROJECT_CONFIG_SCRIPT) $(PROJECT_CONFIG_RUNNER) \
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
