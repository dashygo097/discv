# Project root
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

# Directory layout
BUILD_DIR       := $(PROJECT_ROOT)/build
RTL_DIR         := $(PROJECT_ROOT)/rtl
CONFIG_DIR      := $(PROJECT_ROOT)/config
CONSTRAINT_DIR  := $(PROJECT_ROOT)/constraints
FILELIST_DIR    := $(PROJECT_ROOT)/filelists
SCRIPT_DIR      := $(PROJECT_ROOT)/scripts

# Project configuration
PROJECT_NAME ?= discv
TOP          ?= discv_top

# Common source files
RTL_FILELIST := $(FILELIST_DIR)/rtl.f

# Common utilities
MKDIR := mkdir -p
RM    := rm -rf

# Common targets
.PHONY: dirs clean help

dirs:
	@$(MKDIR) $(BUILD_DIR)

clean:
	@echo "[CLEAN] $(BUILD_DIR)"
	@$(RM) $(BUILD_DIR)

help:
	@echo "Available targets:"
	@echo "  lint     Run RTL lint"
	@echo "  clean    Remove build directory"
