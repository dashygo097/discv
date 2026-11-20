.DEFAULT_GOAL := help
DICFLOW ?= dicflow
export PROJECT_MAKE := $(MAKE)
export SELECT
.PHONY: help init deps-update env config workflow clean distclean status artifacts logs $(MAKECMDGOALS)

help:
	@$(DICFLOW) --help

deps-update:
	+@$(DICFLOW) --root "$(CURDIR)" deps update

init env config workflow clean distclean status artifacts logs:
	+@$(DICFLOW) --root "$(CURDIR)" "$@"

$(filter-out help init deps-update env config workflow clean distclean status artifacts logs,$(MAKECMDGOALS)):
	+@$(DICFLOW) --root "$(CURDIR)" run "$@"
