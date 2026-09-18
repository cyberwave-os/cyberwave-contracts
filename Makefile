# Regenerate the pydantic models from the contract schemas.
#
# Output is committed so consumers need no build step and CI needs no generator
# run to import the models. The backend's test_contract_models.py fails if a
# schema changes without this being re-run.

HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PKG := $(HERE)/cyberwave_contracts

.PHONY: models check

models:
	@python3 $(PKG)/_generate.py
	@ruff format -q $(PKG)/models/*.py
	@ruff check --fix -q $(PKG)/models/*.py || true
	@echo "✅ models regenerated in $(PKG)/models"

# Fails if the committed models are stale. Mirrors what CI asserts, for a dev who
# would rather run make than read the test failure.
# `git status --porcelain`, not `git diff`: a brand-new schema generates a
# brand-new model file, which is *untracked*, and `git diff` does not see
# untracked files -- so the gate went green on exactly the change that added a
# model nobody committed. --porcelain reports modified and untracked alike.
check: models
	@test -z "$$(git status --porcelain -- $(PKG)/models)" \
		|| (echo "❌ committed models are stale or uncommitted:"; \
		    git status --porcelain -- $(PKG)/models; exit 1)
	@echo "✅ committed models match the schemas"
