# Project root
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

# Directory layout
BUILD_DIR       := $(PROJECT_ROOT)/build
GENERATED_DIR   := $(BUILD_DIR)/generated
RTL_DIR         := $(PROJECT_ROOT)/rtl
CONFIG_DIR      := $(PROJECT_ROOT)/config
CONSTRAINT_DIR  := $(PROJECT_ROOT)/constraints
SCRIPT_DIR      := $(PROJECT_ROOT)/scripts

# Generated from Project.toml
RTL_FILELIST := $(GENERATED_DIR)/rtl.f

# Common utilities
MKDIR := mkdir -p
RM    := rm -rf

# Common targets
.PHONY: dirs init clean help

dirs:
	@$(MKDIR) $(BUILD_DIR)

init: dirs
	@echo "[INIT] Initializing Project"
	@test ! -e $(PROJECT_ROOT)/Project.toml || { \
		echo "ERROR: $(PROJECT_ROOT)/Project.toml already exists" >&2; \
		exit 1; \
	}
	@cp $(PROJECT_ROOT)/.project.template.toml $(PROJECT_ROOT)/Project.toml
	@echo "[INIT] $(PROJECT_ROOT)/Project.toml"

clean:
	@$(MAKE) --no-print-directory config-clean lint-clean
	@echo "[CLEAN] Generated flow outputs removed; virtual environment preserved"

help:
	@echo "Available targets:"
	@echo "  init         Init project"
	@echo "  config       Validate Project.toml and generate build configuration"
	@echo "  lint         Run RTL lint"
	@echo "  workflow     Run the ordered stages from Project.toml"
	@echo "  clean        Remove generated flow outputs"
