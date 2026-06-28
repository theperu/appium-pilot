VENV ?= .venv
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
else
BIN := $(VENV)/bin
endif
PY := $(BIN)/python
PYTEST := $(BIN)/pytest

.PHONY: install test test-e2e test-e2e-ios test-e2e-android lint

install:  ## install the package + dev deps into the venv
	$(PY) -m pip install -e ".[dev]"

test:  ## fast unit tests, no device (the after-every-change default)
	$(PYTEST)

test-e2e-android:  ## device-backed E2E against an Android emulator
	$(PYTEST) -m e2e --platform=android

test-e2e-ios:  ## device-backed E2E against an iOS simulator
	$(PYTEST) -m e2e --platform=ios

test-e2e:  ## device-backed E2E on both platforms
	$(PYTEST) -m e2e --platform=both

lint:  ## ruff lint (config in pyproject)
	$(BIN)/ruff check src tests
