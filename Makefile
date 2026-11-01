.DEFAULT_GOAL := help
BOOTSTRAP_PYTHON ?= python3
export PROJECT_ROOT := $(CURDIR)
export PROJECT_MAKE := $(MAKE)
.PHONY: init help $(MAKECMDGOALS)

init:
	@test ! -e Project.toml || { echo 'ERROR: Project.toml already exists' >&2; exit 1; }
	@cp .project.template.toml Project.toml

clean distclean deps-update:
	@"$(BOOTSTRAP_PYTHON)" "$(CURDIR)/scripts/bootstrap.py" "$@"

help $(filter-out init help clean distclean deps-update,$(MAKECMDGOALS)):
	+@if test -x "$(CURDIR)/build/.venv/bin/python"; then \
		"$(CURDIR)/build/.venv/bin/python" "$(CURDIR)/scripts/bootstrap.py" "$@"; \
	else \
		"$(BOOTSTRAP_PYTHON)" "$(CURDIR)/scripts/bootstrap.py" "$@"; \
	fi
