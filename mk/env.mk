# Python bootstrap. This is intentionally independent of Project.toml because
# Python is required to parse Project.toml.
VENV_DIR          := $(BUILD_DIR)/.venv
VENV_PYTHON       := $(VENV_DIR)/bin/python
VENV_STAMP        := $(VENV_DIR)/.ready
VENV_SETUP_SCRIPT := $(SCRIPT_DIR)/config/setup_venv.sh
VENV_REQUIREMENTS := $(SCRIPT_DIR)/config/requirements.txt
BOOTSTRAP_PYTHON  ?= python3

.PHONY: env

env: $(VENV_STAMP)

$(VENV_STAMP): $(VENV_SETUP_SCRIPT) $(VENV_REQUIREMENTS) \
		$(SCRIPT_DIR)/common/check_env.sh
	@PYTHON_BIN=$(BOOTSTRAP_PYTHON) \
	PROJECT_VENV_DIR=$(VENV_DIR) \
	$(VENV_SETUP_SCRIPT)
	@touch $@
