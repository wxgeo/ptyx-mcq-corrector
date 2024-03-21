ui:
	@./.build_ui

tox:
	poetry run black .
	poetry run tox

fix:
	poetry run black .
	poetry run ruff --fix ptyx_mcq_corrector tests

help:
	@cat Makefile

.PHONY: ui help

