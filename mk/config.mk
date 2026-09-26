# Project configuration
PROJECT_CONFIG        := $(PROJECT_ROOT)/Project.toml
PROJECT_CONFIG_SCRIPT := $(SCRIPT_DIR)/config/project_config.py
PROJECT_CONFIG_RUNNER := $(SCRIPT_DIR)/config/run.sh
CONFIG_MANIFEST       := $(GENERATED_DIR)/manifest.json
CONFIG_MAKEFILE       := $(GENERATED_DIR)/project.mk
PROJECT_ENV           := $(GENERATED_DIR)/project.env
PYTHON                ?= $(VENV_PYTHON)

# Stage implementation targets run in a fresh Make process after configuration
# has been synchronized, so they always consume the current generated values.
ifneq ($(filter config lint lint-run synth synth-run sim sim-run sim-build sim-build-run workflow,$(MAKECMDGOALS)),)
-include $(CONFIG_MAKEFILE)
endif

.PHONY: config config-clean

config: env
	@echo "[CONFIG] Synchronizing project configuration"
	@$(MKDIR) $(GENERATED_DIR)
	@PROJECT_ROOT=$(PROJECT_ROOT) \
	PROJECT_CONFIG=$(PROJECT_CONFIG) \
	PROJECT_CONFIG_SCRIPT=$(PROJECT_CONFIG_SCRIPT) \
	GENERATED_DIR=$(GENERATED_DIR) \
	PYTHON=$(PYTHON) \
	$(PROJECT_CONFIG_RUNNER)

config-clean:
	@echo "[CLEAN] config"
	@$(RM) $(GENERATED_DIR)
