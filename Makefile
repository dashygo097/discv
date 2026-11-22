.DEFAULT_GOAL := help
DICFLOW ?= dicflow
export PROJECT_MAKE := $(MAKE)
export SELECT

shell_quote = '$(subst ','"'"',$(1))'
DICFLOW_CMD = $(DICFLOW) --root $(call shell_quote,$(CURDIR)) \
	$(if $(ENGINE),--engine=$(call shell_quote,$(ENGINE))) \
	$(if $(COLOR),--color=$(call shell_quote,$(COLOR))) \
	$(if $(filter 1,$(VERBOSE)),--verbose)

WRAPPER_TARGETS := help init deps-update env config workflow clean distclean status artifacts logs run
.PHONY: $(WRAPPER_TARGETS) $(MAKECMDGOALS)

help:
	@$(DICFLOW_CMD) --help
	@printf '%s\n' '' 'Make examples:' \
		'  make init TEMPLATE=path/to/template.toml [DRY_RUN=1] [FORCE=1]' \
		'  make run STAGE=sim-run PROGRAM=build/program.bin' \
		'  make logs SELECT=sta JSON=1' \
		'  Common options: ENGINE=path/to/dicflow COLOR=never VERBOSE=1'

deps-update:
	@$(DICFLOW_CMD) deps update

init:
	@test -n $(call shell_quote,$(TEMPLATE)) || { \
		printf '%s\n' 'Usage: make init TEMPLATE=path/to/template.toml [DRY_RUN=1] [FORCE=1]' >&2; \
		exit 2; \
	}
	@$(DICFLOW_CMD) init --template=$(call shell_quote,$(TEMPLATE)) \
		$(if $(filter 1,$(DRY_RUN)),--dry-run) $(if $(filter 1,$(FORCE)),--force)

status artifacts logs:
	@$(DICFLOW_CMD) "$@" $(if $(filter 1,$(JSON)),--json)

env config clean distclean:
	@$(DICFLOW_CMD) "$@"

workflow:
	+@$(DICFLOW_CMD) workflow

run:
	@test -n $(call shell_quote,$(STAGE)) || { \
		printf '%s\n' 'Usage: make run STAGE=stage-name' >&2; \
		exit 2; \
	}
	+@$(DICFLOW_CMD) run -- $(call shell_quote,$(STAGE))

$(filter-out $(WRAPPER_TARGETS),$(MAKECMDGOALS)):
	+@$(DICFLOW_CMD) run -- $(call shell_quote,$@)
