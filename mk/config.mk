# Project configuration
PROJECT_CONFIG        := $(BUILD_DIR)/Project.toml
PROJECT_CONFIG_SCRIPT := $(SCRIPT_DIR)/config/project_config.py
CONFIG_MANIFEST       := $(GENERATED_DIR)/manifest.json
CONFIG_MAKEFILE       := $(GENERATED_DIR)/project.mk
CONFIG_OUTPUTS        := $(RTL_FILELIST) $(CONFIG_MAKEFILE) $(CONFIG_MANIFEST)
CONFIG_STAMP          := $(GENERATED_DIR)/.done
VENV_PYTHON           := $(BUILD_DIR)/.venv/bin/python
PYTHON                ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)

.PHONY: config config-clean

config: $(CONFIG_OUTPUTS)

$(CONFIG_STAMP): $(PROJECT_CONFIG) $(PROJECT_CONFIG_SCRIPT)
	@echo "[CONFIG] Generating project configuration"
	@$(MKDIR) $(GENERATED_DIR)
	@$(PYTHON) $(PROJECT_CONFIG_SCRIPT) generate \
		$(PROJECT_CONFIG) \
		--project-root $(PROJECT_ROOT) \
		--output $(GENERATED_DIR)
	@touch $@

# Let downstream stages depend on individual generated files while retaining a
# single generation recipe compatible with the older GNU Make on CentOS 7.
$(CONFIG_OUTPUTS): $(CONFIG_STAMP)
	@if ! test -f $@; then \
		echo "[CONFIG] Regenerating missing output: $@"; \
		$(PYTHON) $(PROJECT_CONFIG_SCRIPT) generate \
			$(PROJECT_CONFIG) \
			--project-root $(PROJECT_ROOT) \
			--output $(GENERATED_DIR); \
		touch $(CONFIG_STAMP); \
	fi

config-clean:
	@echo "[CLEAN] config"
	@$(RM) $(GENERATED_DIR)
