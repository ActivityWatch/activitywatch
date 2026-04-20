# =====================================
# Makefile for the ActivityWatch bundle
# =====================================
#
# [GUIDE] How to install from source:
#  - https://activitywatch.readthedocs.io/en/latest/installing-from-source.html
#
# We recommend creating and activating a Python virtualenv before building.
# Instructions on how to do this can be found in the guide linked above.
.PHONY: build install test clean clean_all doctor venv-check

SHELL := /usr/bin/env bash

OS := $(shell uname -s)

# =====================================
# Helper Functions & Checks
# =====================================

# Check if running in a Python virtual environment
# Returns: 0 if in venv, 1 otherwise
# Usage: $(call in_venv)
define in_venv
$(shell python3 -c "import sys; print(1 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 0)" 2>/dev/null || echo 0)
endef

# Get Python version (major.minor)
# Usage: $(call python_version)
define python_version
$(shell python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
endef

# Get setuptools version
# Usage: $(call setuptools_version)
define setuptools_version
$(shell python3 -c "import setuptools; print(setuptools.__version__)" 2>/dev/null || echo "0.0.0")
endef

# Compare versions (returns 1 if v1 > v2, 0 otherwise)
# Usage: $(call version_gt,<v1>,<v2>)
define version_gt
$(shell python3 -c "from packaging.version import Version; print(1 if Version('$1') > Version('$2') else 0)" 2>/dev/null || python3 -c "import sys; print(1 if tuple(map(int, '$1'.split('.'))) > tuple(map(int, '$2'.split('.'))) else 0)" 2>/dev/null || echo 0)
endef

# =====================================
# Virtual Environment Check
# =====================================

VENVS := .venv venv
ACTIVE_VENV := $(firstword $(wildcard $(VENVS)))

venv-check:
	@echo "Checking virtual environment..."
	@IN_VENV=$(call in_venv); \
	if [ "$$IN_VENV" != "1" ]; then \
		echo ""; \
		echo "==========================================================================="; \
		echo "[ERROR] Not running in a Python virtual environment!"; \
		echo "==========================================================================="; \
		echo ""; \
		echo "Running make build outside a venv can:"; \
		echo "  - Pollute your global Python environment"; \
		echo "  - Cause version conflicts with other packages"; \
		echo "  - Require root/sudo privileges"; \
		echo ""; \
		echo "Recommended setup:"; \
		echo ""; \
		echo "  # Create a virtual environment (do this once)"; \
		if [ -n "$(ACTIVE_VENV)" ]; then \
			echo "  python3 -m venv $(ACTIVE_VENV)      # <-- already exists"; \
		else \
			echo "  python3 -m venv .venv"; \
		fi; \
		echo ""; \
		echo "  # Activate the virtual environment (do this in every new shell)"; \
		if [ "$$(basename $$SHELL)" = "fish" ]; then \
			echo "  source .venv/bin/activate.fish   # for fish shell"; \
		else \
			echo "  source .venv/bin/activate        # for bash/zsh"; \
		fi; \
		echo ""; \
		echo "  # Then run:"; \
		echo "  make build"; \
		echo ""; \
		echo "==========================================================================="; \
		echo ""; \
		echo "If you KNOW what you're doing and want to skip this check:"; \
		echo "  export SKIP_VENV_CHECK=1"; \
		echo "  make build"; \
		echo ""; \
		echo "==========================================================================="; \
		exit 1; \
	else \
		echo "  ✓ Running in virtual environment"; \
		echo "    VIRTUAL_ENV: $$VIRTUAL_ENV"; \
	fi; \
	echo ""

# =====================================
# Doctor: Check all dependencies
# =====================================

doctor: venv-check
	@echo "==========================================================================="
	@echo "ActivityWatch Build Environment Doctor"
	@echo "==========================================================================="
	@echo ""
	@echo "--- Python Environment ---"
	@echo ""
	@echo -n "  Python: "
	@if command -v python3 >/dev/null 2>&1; then \
		PY_VER=$$(python3 --version 2>&1); \
		echo "✓ $$PY_VER"; \
	else \
		echo "✗ python3 not found in PATH"; \
		ERRORS=1; \
	fi

	@echo -n "  pip: "
	@if python3 -m pip --version >/dev/null 2>&1; then \
		PIP_VER=$$(python3 -m pip --version 2>&1 | cut -d' ' -f2); \
		echo "✓ $$PIP_VER"; \
	else \
		echo "✗ pip not available"; \
		ERRORS=1; \
	fi

	@echo -n "  poetry: "
	@if command -v poetry >/dev/null 2>&1; then \
		POETRY_VER=$$(poetry --version 2>&1 | sed 's/.*version \([0-9.]*\).*/\1/'); \
		echo "✓ $$POETRY_VER"; \
	else \
		echo "✗ poetry not found in PATH"; \
		echo "    Install with: pip3 install poetry==1.4.2"; \
		ERRORS=1; \
	fi

	@echo -n "  setuptools: "
	@SETUPTOOLS_VER=$(call setuptools_version); \
	if [ -n "$$SETUPTOOLS_VER" ] && [ "$$SETUPTOOLS_VER" != "0.0.0" ]; then \
		echo "✓ $$SETUPTOOLS_VER"; \
		NEEDS_UPDATE=$(call version_gt,49.1.1,$$SETUPTOOLS_VER); \
		if [ "$$NEEDS_UPDATE" = "1" ]; then \
			echo "    ⚠ Version <= 49.1.1, may cause issues (see: pypa/setuptools#1963)"; \
			echo "      Will be automatically updated during make build"; \
		fi; \
	else \
		echo "✗ Could not determine setuptools version"; \
		ERRORS=1; \
	fi

	@echo ""
	@echo "--- Node.js Environment (for web UI) ---"
	@echo ""
	@echo -n "  node: "
	@if command -v node >/dev/null 2>&1; then \
		NODE_VER=$$(node --version 2>&1); \
		echo "✓ $$NODE_VER"; \
	else \
		echo "⚠ node not found in PATH (only needed for web UI build)"; \
		echo "    SKIP_WEBUI=true can be used to skip web UI build"; \
	fi

	@echo -n "  npm: "
	@if command -v npm >/dev/null 2>&1; then \
		NPM_VER=$$(npm --version 2>&1); \
		echo "✓ $$NPM_VER"; \
	else \
		echo "⚠ npm not found (only needed for web UI build)"; \
	fi

	@echo ""
	@echo "--- Rust Environment (for aw-server-rust) ---"
	@echo ""
	@echo -n "  rustc: "
	@if command -v rustc >/dev/null 2>&1; then \
		RUST_VER=$$(rustc --version 2>&1); \
		echo "✓ $$RUST_VER"; \
	else \
		echo "⚠ rustc not found in PATH (only needed for aw-server-rust)"; \
		echo "    SKIP_SERVER_RUST=true can be used to skip Rust build"; \
	fi

	@echo -n "  cargo: "
	@if command -v cargo >/dev/null 2>&1; then \
		CARGO_VER=$$(cargo --version 2>&1 | cut -d' ' -f2); \
		echo "✓ $$CARGO_VER"; \
	else \
		echo "⚠ cargo not found (only needed for aw-server-rust)"; \
	fi

	@echo ""
	@echo "--- Git Submodules ---"
	@echo ""
	@for module in aw-core aw-client aw-server; do \
		echo -n "  $$module: "; \
		if [ -d "$$module/.git" ]; then \
			echo "✓ initialized"; \
		else \
			echo "✗ not initialized"; \
			echo "    Run: git submodule update --init --recursive"; \
			ERRORS=1; \
		fi; \
	done

	@echo ""
	@echo "==========================================================================="
	@echo "Summary"
	@echo "==========================================================================="
	@echo ""
	@echo "Virtual environment: ✓ Active"
	@echo "  Path: $$VIRTUAL_ENV"
	@echo ""
	@if [ -n "$$ERRORS" ]; then \
		echo "❌ Some issues found. Please fix them before building."; \
		exit 1; \
	else \
		echo "✅ All required dependencies look good!"; \
		echo ""; \
		echo "   You can now run:"; \
		echo "     make build"; \
		echo ""; \
		echo "   Or with options:"; \
		echo "     make build SKIP_WEBUI=true"; \
		echo "     make build SKIP_SERVER_RUST=true"; \
		echo "     make build RELEASE=true"; \
		echo ""; \
	fi

ifeq ($(TAURI_BUILD),true)
	SUBMODULES := aw-core aw-client aw-server aw-server-rust aw-watcher-afk aw-watcher-window aw-tauri
	# Include awatcher on Linux (Wayland-compatible window watcher)
	ifeq ($(OS),Linux)
		SUBMODULES := $(SUBMODULES) awatcher
	endif
else
	SUBMODULES := aw-core aw-client aw-qt aw-server aw-server-rust aw-watcher-afk aw-watcher-window
endif

# Exclude aw-server-rust if SKIP_SERVER_RUST is true
ifeq ($(SKIP_SERVER_RUST),true)
	SUBMODULES := $(filter-out aw-server-rust,$(SUBMODULES))
endif
# Include extras if AW_EXTRAS is true
ifeq ($(AW_EXTRAS),true)
	SUBMODULES := $(SUBMODULES) aw-notify aw-watcher-input
endif

# A function that checks if a target exists in a Makefile
# Usage: $(call has_target,<dir>,<target>)
define has_target
$(shell make -q -C $1 $2 >/dev/null 2>&1; if [ $$? -eq 0 -o $$? -eq 1 ]; then echo $1; fi)
endef

# Submodules with test/package/lint/typecheck targets
TESTABLES := $(foreach dir,$(SUBMODULES),$(call has_target,$(dir),test))
PACKAGEABLES := $(foreach dir,$(SUBMODULES),$(call has_target,$(dir),package))
LINTABLES := $(foreach dir,$(SUBMODULES),$(call has_target,$(dir),lint))
TYPECHECKABLES := $(foreach dir,$(SUBMODULES),$(call has_target,$(dir),typecheck))

# When building with Tauri, aw-server-rust is built as aw-sync only (not full server),
# so exclude it from the standard package target
ifeq ($(TAURI_BUILD),true)
	PACKAGEABLES := $(filter-out aw-server-rust aw-server, $(PACKAGEABLES))
endif

# Build mode: release vs debug
ifeq ($(RELEASE), false)
	targetdir := debug
else
	targetdir := release
endif

# The `build` target
# ------------------
#
# What it does:
#  - Installs all the Python modules
#  - Builds the web UI and bundles it with aw-server
build: build-pre-check aw-core/.git
	@echo "==========================================================================="
	@echo "Building ActivityWatch"
	@echo "==========================================================================="
	@echo ""
	@echo "Configuration:"
	@echo "  RELEASE: $(RELEASE)"
	@echo "  TAURI_BUILD: $(TAURI_BUILD)"
	@echo "  SKIP_WEBUI: $(SKIP_WEBUI)"
	@echo "  SKIP_SERVER_RUST: $(SKIP_SERVER_RUST)"
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "Checking setuptools version..."
	@SETUPTOOLS_VER=$(call setuptools_version); \
	NEEDS_UPDATE=$(call version_gt,49.1.1,$$SETUPTOOLS_VER); \
	if [ "$$NEEDS_UPDATE" = "1" ]; then \
		echo "  ⚠ setuptools version $$SETUPTOOLS_VER is <= 49.1.1"; \
		echo "    Updating to avoid issue: pypa/setuptools#1963"; \
		python3 -m pip install 'setuptools>49.1.1'; \
	else \
		echo "  ✓ setuptools version $$SETUPTOOLS_VER is OK (> 49.1.1)"; \
		echo "    Skipping setuptools update workaround"; \
	fi
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "Building submodules..."
	@for module in $(SUBMODULES); do \
		echo ""; \
		echo "==========================================================================="; \
		echo "Building $$module"; \
		echo "==========================================================================="; \
		if [ "$$module" = "aw-server-rust" ] && [ "$(TAURI_BUILD)" = "true" ]; then \
			make --directory=$$module aw-sync SKIP_WEBUI=$(SKIP_WEBUI) || { echo "Error in $$module aw-sync"; exit 2; }; \
		else \
			make --directory=$$module build SKIP_WEBUI=$(SKIP_WEBUI) || { echo "Error in $$module build"; exit 2; }; \
		fi; \
	done
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "Finalizing build..."
#   The below is needed due to: https://github.com/ActivityWatch/activitywatch/issues/173
	make --directory=aw-client build
	make --directory=aw-core build
#	Needed to ensure that the server has the correct version set
	python3 -c "import aw_server; print('aw_server version:', aw_server.__version__)"
	@echo ""
	@echo "==========================================================================="
	@echo "Build complete!"
	@echo "==========================================================================="

# build-pre-check: venv check, but allow skip via SKIP_VENV_CHECK
build-pre-check:
	@if [ -z "$(SKIP_VENV_CHECK)" ] || [ "$(SKIP_VENV_CHECK)" = "0" ]; then \
		$(MAKE) venv-check; \
	else \
		echo "⚠ SKIP_VENV_CHECK=1 is set, skipping venv check"; \
		echo "  This may pollute your global Python environment."; \
		echo ""; \
	fi


# Install
# -------
#
# Installs things like desktop/menu shortcuts.
# Might in the future configure autostart on the system.
ifneq ($(TAURI_BUILD),true)
install:
	make --directory=aw-qt install
# Installation is already happening in the `make build` step currently.
# We might want to change this.
# We should also add some option to install as user (pip3 install --user)
endif

# Update
# ------
#
# Pulls the latest version, updates all the submodules, then runs `make build`.
update:
	git pull
	git submodule update --init --recursive
	make build


lint:
	@for module in $(LINTABLES); do \
		echo "Linting $$module"; \
		make --directory=$$module lint || { echo "Error in $$module lint"; exit 2; }; \
	done

typecheck:
	@for module in $(TYPECHECKABLES); do \
		echo "Typechecking $$module"; \
		make --directory=$$module typecheck || { echo "Error in $$module typecheck"; exit 2; }; \
	done

# Uninstall
# ---------
#
# Uninstalls all the Python modules.
uninstall:
	modules=$$(pip3 list --format=legacy | grep 'aw-' | grep -o '^aw-[^ ]*'); \
	for module in $$modules; do \
		echo "Uninstalling $$module"; \
		pip3 uninstall -y $$module; \
	done

test:
	@for module in $(TESTABLES); do \
		echo "Running tests for $$module"; \
		if [ -f "$$module/pyproject.toml" ]; then \
			(cd $$module && poetry run make test) || { echo "Error in $$module tests"; exit 2; }; \
		else \
			make -C $$module test || { echo "Error in $$module tests"; exit 2; }; \
		fi; \
	done

.PHONY: test-integration test-integration-help

AW_TEST_TIMEOUT ?= 180
AW_PYTEST_TIMEOUT ?= 120

test-integration-help:
	@echo "==========================================================================="
	@echo "ActivityWatch Integration Tests"
	@echo "==========================================================================="
	@echo ""
	@echo "Usage:"
	@echo "  make test-integration                    # Use aw-server from PATH"
	@echo "  AW_SERVER_BIN=./path/to/aw-server make test-integration  # Use specific binary"
	@echo ""
	@echo "Environment Variables (all optional):"
	@echo "  AW_SERVER_BIN     Path to aw-server binary (default: 'aw-server' from PATH)"
	@echo "                    Examples: ./dist/activitywatch/aw-server-rust/aw-server"
	@echo "                              ./dist/activitywatch/aw-server"
	@echo "  AW_SERVER_PORT    Port to use (default: 5666 for testing)"
	@echo "  AW_SERVER_TIMEOUT Server startup timeout in seconds (default: 30)"
	@echo "  AW_SERVER_POLL    Poll interval in seconds (default: 1.0)"
	@echo "  AW_LOG_LINES      Number of log lines to show on failure (default: 100)"
	@echo "  AW_SERVER_ARGS    Extra arguments (default: '--testing')"
	@echo "  AW_TEST_TIMEOUT   Global test timeout in seconds (default: 180)"
	@echo "  AW_PYTEST_TIMEOUT Per-test pytest timeout in seconds (default: 120)"
	@echo ""
	@echo "Examples:"
	@echo "  # Run with aw-server from PATH"
	@echo "  make test-integration"
	@echo ""
	@echo "  # Run with Tauri-built aw-server-rust"
	@echo "  AW_SERVER_BIN=./dist/activitywatch/aw-server-rust/aw-server make test-integration"
	@echo ""
	@echo "  # Run with custom port and longer timeout"
	@echo "  AW_SERVER_PORT=5777 AW_SERVER_TIMEOUT=60 AW_TEST_TIMEOUT=300 make test-integration"
	@echo ""
	@echo "What it tests:"
	@echo "  1. Server starts and responds to /api/0/info (no fixed sleep)"
	@echo "  2. /api/0/info returns version and hostname"
	@echo "  3. /api/0/buckets returns valid data"
	@echo "  4. No ERROR/panic indicators in logs"
	@echo ""
	@echo "Timeout Protection (prevents hanging in CI):"
	@echo "  - Global timeout: $(AW_TEST_TIMEOUT)s (entire test run)"
	@echo "  - Per-test timeout: $(AW_PYTEST_TIMEOUT)s (individual test)"
	@echo "  - Server startup timeout: $(AW_SERVER_TIMEOUT)s (default)"
	@echo ""
	@echo "Error Classification (diagnosable):"
	@echo "  - LAUNCH_FAILED:    Server binary not found or failed to start"
	@echo "  - EARLY_EXIT:       Server started but exited with error"
	@echo "  - STARTUP_TIMEOUT:  Server never became responsive"
	@echo "  - API_ERROR:        API request returned non-200 status"
	@echo "  - ASSERTION_FAILED: API assertion failed (missing fields)"
	@echo "  - LOG_ERROR:        Server logs contain ERROR/panic"
	@echo ""
	@echo "On failure/timeout:"
	@echo "  - Prints last N lines of stdout and stderr for diagnosis"
	@echo "  - Shows error type classification"
	@echo "  - Shows server PID, port, exit code"
	@echo "==========================================================================="

test-integration:
	@echo "==========================================================================="
	@echo "Integration Testing ActivityWatch Server"
	@echo "==========================================================================="
	@echo ""
	@echo "Environment:"
	@echo "  AW_SERVER_BIN:     ${AW_SERVER_BIN:-aw-server (from PATH)}"
	@echo "  AW_SERVER_PORT:    ${AW_SERVER_PORT:-5666}"
	@echo "  AW_SERVER_TIMEOUT: ${AW_SERVER_TIMEOUT:-30}s"
	@echo "  AW_TEST_TIMEOUT:   $(AW_TEST_TIMEOUT)s (global)"
	@echo "  AW_PYTEST_TIMEOUT: $(AW_PYTEST_TIMEOUT)s (per-test)"
	@echo ""
	@echo "For help: make test-integration-help"
	@echo "==========================================================================="
	@echo ""
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		if command -v gtimeout >/dev/null 2>&1; then \
			echo "Using gtimeout for global timeout protection..."; \
			gtimeout --signal=SIGKILL $(AW_TEST_TIMEOUT) \
				pytest scripts/tests/integration_tests.py -v \
					--timeout=$(AW_PYTEST_TIMEOUT) \
					-o timeout_method=thread; \
		else \
			echo "Note: gtimeout not found (install with: brew install coreutils)"; \
			echo "Running without global timeout wrapper, relying on pytest-timeout..."; \
			pytest scripts/tests/integration_tests.py -v \
				--timeout=$(AW_PYTEST_TIMEOUT) \
				-o timeout_method=thread; \
		fi; \
	else \
		echo "Using timeout for global timeout protection..."; \
		timeout --signal=SIGKILL $(AW_TEST_TIMEOUT) \
			pytest scripts/tests/integration_tests.py -v \
				--timeout=$(AW_PYTEST_TIMEOUT) \
				-o timeout_method=thread; \
	fi

%/.git:
	git submodule update --init --recursive

ifeq ($(TAURI_BUILD),true)
	ICON := "aw-tauri/src-tauri/icons/icon.png"
else
	ICON := "aw-qt/media/logo/logo.png"
endif

aw-qt/media/logo/logo.icns:
	mkdir -p build/MyIcon.iconset
	sips -z 16 16     $(ICON) --out build/MyIcon.iconset/icon_16x16.png
	sips -z 32 32     $(ICON) --out build/MyIcon.iconset/icon_16x16@2x.png
	sips -z 32 32     $(ICON) --out build/MyIcon.iconset/icon_32x32.png
	sips -z 64 64     $(ICON) --out build/MyIcon.iconset/icon_32x32@2x.png
	sips -z 128 128   $(ICON) --out build/MyIcon.iconset/icon_128x128.png
	sips -z 256 256   $(ICON) --out build/MyIcon.iconset/icon_128x128@2x.png
	sips -z 256 256   $(ICON) --out build/MyIcon.iconset/icon_256x256.png
	sips -z 512 512   $(ICON) --out build/MyIcon.iconset/icon_256x256@2x.png
	sips -z 512 512   $(ICON) --out build/MyIcon.iconset/icon_512x512.png
	cp				  $(ICON)       build/MyIcon.iconset/icon_512x512@2x.png
	iconutil -c icns build/MyIcon.iconset
	rm -R build/MyIcon.iconset
	mv build/MyIcon.icns aw-qt/media/logo/logo.icns

dist/ActivityWatch.app: aw-qt/media/logo/logo.icns
ifeq ($(TAURI_BUILD),true)
	scripts/package/build_app_tauri.sh
else
	pyinstaller --clean --noconfirm aw.spec
endif

dist/ActivityWatch.dmg: dist/ActivityWatch.app
	@echo ""
	@echo "==========================================================================="
	@echo "Building ActivityWatch.dmg"
	@echo "==========================================================================="
	@echo ""
	@echo "Configuration:"
	@echo "  AW_SIGN:     $(AW_SIGN:-false)"
	@echo "  AW_NOTARIZE: $(AW_NOTARIZE:-false)"
	@echo "  AW_IDENTITY: $(if $(AW_IDENTITY),$(AW_IDENTITY),$(if $(APPLE_PERSONALID),$(APPLE_PERSONALID),not set))"
	@echo ""
	@if [ -n "$(AW_SIGN)" ] && [ "$(AW_SIGN)" = "true" ]; then \
		echo "[INFO] AW_SIGN=true: Will sign .app and .dmg after building"; \
		echo "       Identity: $(if $(AW_IDENTITY),$(AW_IDENTITY),$(if $(APPLE_PERSONALID),$(APPLE_PERSONALID),not set))"; \
	fi
	@if [ -n "$(AW_NOTARIZE)" ] && [ "$(AW_NOTARIZE)" = "true" ]; then \
		echo "[INFO] AW_NOTARIZE=true: Will notarize .app and .dmg after building"; \
		echo "       Requires: APPLE_EMAIL, APPLE_PASSWORD, APPLE_TEAMID"; \
	fi
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[BUILD] Creating DMG with dmgbuild..."
	@echo "  [ACTION] pip install dmgbuild"
	@echo "  [ACTION] dmgbuild -s scripts/package/dmgbuild-settings.py -D app=dist/ActivityWatch.app \"ActivityWatch\" dist/ActivityWatch.dmg"
	@echo ""
	pip install dmgbuild
	dmgbuild -s scripts/package/dmgbuild-settings.py -D app=dist/ActivityWatch.app "ActivityWatch" dist/ActivityWatch.dmg
	@echo ""
	@echo "[OK] DMG created: dist/ActivityWatch.dmg"
	
	# Optional: Sign .app and .dmg (if AW_SIGN=true)
	@if [ -n "$(AW_SIGN)" ] && [ "$(AW_SIGN)" = "true" ]; then \
		echo ""; \
		echo "---------------------------------------------------------------------------"; \
		echo "[SIGN] Signing .app bundle (inside-out order)..."; \
		echo ""; \
		AW_SIGN=true AW_IDENTITY="$(if $(AW_IDENTITY),$(AW_IDENTITY),$(if $(APPLE_PERSONALID),$(APPLE_PERSONALID),))" \
			AW_NOTARIZE=false AW_DRY_RUN="$(if $(AW_DRY_RUN),$(AW_DRY_RUN),false)" \
			bash scripts/notarize.sh; \
	fi
	
	# Optional: Notarize (if AW_NOTARIZE=true)
	@if [ -n "$(AW_NOTARIZE)" ] && [ "$(AW_NOTARIZE)" = "true" ]; then \
		echo ""; \
		echo "---------------------------------------------------------------------------"; \
		echo "[NOTARIZE] Submitting to Apple for notarization..."; \
		echo "  Note: This may take several minutes"; \
		echo ""; \
		AW_SIGN="$(if $(AW_SIGN),$(AW_SIGN),false)" \
			AW_NOTARIZE=true \
			AW_DRY_RUN="$(if $(AW_DRY_RUN),$(AW_DRY_RUN),false)" \
			bash scripts/notarize.sh; \
	fi
	
	@echo ""
	@echo "==========================================================================="
	@echo "ActivityWatch.dmg Build Complete"
	@echo "==========================================================================="
	@echo ""
	@echo "Output:"
	@echo "  dist/ActivityWatch.app"
	@echo "  dist/ActivityWatch.dmg"
	@echo ""
	@echo "Troubleshooting Commands:"
	@echo "  # Verify signature:"
	@echo "    codesign -v --verify --strict dist/ActivityWatch.app"
	@echo "    codesign -v --verify --strict dist/ActivityWatch.dmg"
	@echo ""
	@echo "  # Show signature details:"
	@echo "    codesign -dvvv dist/ActivityWatch.app"
	@echo ""
	@echo "  # Check notarization history:"
	@echo "    xcrun notarytool history --keychain-profile activitywatch-notarization"
	@echo ""
	@echo "  # Check stapler validation:"
	@echo "    xcrun stapler validate dist/ActivityWatch.app"
	@echo "    xcrun stapler validate dist/ActivityWatch.dmg"
	@echo ""
	@echo "==========================================================================="

dist/notarize:
	@echo ""
	@echo "==========================================================================="
	@echo "Notarizing ActivityWatch"
	@echo "==========================================================================="
	@echo ""
	@echo "Usage:"
	@echo "  make dist/notarize                           # Run notarize.sh"
	@echo "  make dist/notarize AW_SIGN=true              # Also sign first"
	@echo "  make dist/notarize AW_NOTARIZE=true          # Also notarize"
	@echo "  make dist/notarize AW_SIGN=true AW_NOTARIZE=true  # Sign and notarize"
	@echo ""
	./scripts/notarize.sh

package: package-pre-check
	@echo ""
	@echo "==========================================================================="
	@echo "ActivityWatch Packaging"
	@echo "==========================================================================="
	@echo ""
	@echo "Configuration:"
	@echo "  TAURI_BUILD:           $(TAURI_BUILD)"
	@echo "  RELEASE:               $(RELEASE)"
	@echo "  Target:                $(targetdir)"
	@echo "  Packageables:          $(PACKAGEABLES)"
	@echo "  PACKAGE_STRICT:        $(PACKAGE_STRICT:-false)"
	@echo "  WINDOWS_VERIFY_STRICT: $(WINDOWS_VERIFY_STRICT:-false)"
	@echo ""
	@echo "Verification Modes:"
	@echo "  - PACKAGE_STRICT=true:         Fail on any verification errors (general)"
	@echo "  - WINDOWS_VERIFY_STRICT=true:  Fail if zip contents differ from source (Windows only)"
	@echo ""
	@echo "Recommended for CI:"
	@echo "  make package PACKAGE_STRICT=true WINDOWS_VERIFY_STRICT=true"
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[CLEAN] Removing old dist directory..."
	@echo "  [ACTION] rm -rf dist"
	rm -rf dist
	@echo "  [OK] dist directory removed"
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[CREATE] Creating directory structure..."
	@echo "  [ACTION] mkdir -p dist/activitywatch"
	mkdir -p dist/activitywatch
	@echo "  [OK] dist/activitywatch created"
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[PACKAGE] Building submodules..."
	@for dir in $(PACKAGEABLES); do \
		echo ""; \
		echo "==========================================================================="; \
		echo "[SUBMODULE] $$dir"; \
		echo "==========================================================================="; \
		echo "  [ACTION] make --directory=$$dir package"; \
		if make --directory=$$dir package; then \
			echo "  [OK] $$dir packaged successfully"; \
		else \
			echo "  [ERROR] Failed to package $$dir"; \
			exit 2; \
		fi; \
		echo ""; \
		echo "  [ACTION] cp -r $$dir/dist/$$dir dist/activitywatch"; \
		if cp -r $$dir/dist/$$dir dist/activitywatch; then \
			echo "  [OK] Copied $$dir to dist/activitywatch"; \
			find dist/activitywatch/$$dir -type f -name "*" | head -10; \
		else \
			echo "  [ERROR] Failed to copy $$dir"; \
			exit 2; \
		fi; \
	done
	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[POST-PROCESS] Additional steps..."

ifeq ($(TAURI_BUILD),true)
	@echo ""
	@echo "==========================================================================="
	@echo "[TAURI] Tauri-specific packaging"
	@echo "==========================================================================="
	@echo "  [ACTION] mkdir -p dist/activitywatch/aw-server-rust"
	mkdir -p dist/activitywatch/aw-server-rust
	@echo "  [OK] dist/activitywatch/aw-server-rust created"
	@echo ""
	@echo "  [ACTION] cp aw-server-rust/target/$(targetdir)/aw-sync dist/activitywatch/aw-server-rust/aw-sync"
	cp aw-server-rust/target/$(targetdir)/aw-sync dist/activitywatch/aw-server-rust/aw-sync
	@echo "  [OK] aw-sync copied from aw-server-rust/target/$(targetdir)/aw-sync"
	@echo "  [INFO] Source: aw-server-rust/target/$(targetdir)/aw-sync"
	@echo "  [INFO] Target: dist/activitywatch/aw-server-rust/aw-sync"
else
	@echo ""
	@echo "==========================================================================="
	@echo "[NON-TAURI] aw-qt rearrangement"
	@echo "==========================================================================="
	@echo "  [ACTION] mv dist/activitywatch/aw-qt aw-qt-tmp"
	mv dist/activitywatch/aw-qt aw-qt-tmp
	@echo "  [OK] aw-qt moved to aw-qt-tmp"
	@echo ""
	@echo "  [ACTION] mv aw-qt-tmp/* dist/activitywatch"
	mv aw-qt-tmp/* dist/activitywatch
	@echo "  [OK] aw-qt contents moved to dist/activitywatch"
	@echo ""
	@echo "  [ACTION] rmdir aw-qt-tmp"
	rmdir aw-qt-tmp
	@echo "  [OK] aw-qt-tmp removed"
endif

	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[CLEANUP] Removing problem-causing files..."
	@echo "  [ACTION] Removing libraries that cause runtime issues..."
	@echo ""
	@echo "  - libdrm.so.2 (see: https://github.com/ActivityWatch/activitywatch/issues/161)"
	rm -f dist/activitywatch/libdrm.so.2
	@echo "    [OK] libdrm.so.2 removed"
	
	@echo "  - libharfbuzz.so.0 (see: https://github.com/ActivityWatch/activitywatch/issues/660)"
	rm -f dist/activitywatch/libharfbuzz.so.0
	@echo "    [OK] libharfbuzz.so.0 removed"
	
	@echo "  - libfontconfig.so.1 (symbol lookup error)"
	rm -f dist/activitywatch/libfontconfig.so.1
	@echo "    [OK] libfontconfig.so.1 removed"
	
	@echo "  - libfreetype.so.6 (symbol lookup error)"
	rm -f dist/activitywatch/libfreetype.so.6
	@echo "    [OK] libfreetype.so.6 removed"
	
	@echo "  - pytz (unnecessary)"
	rm -rf dist/activitywatch/pytz
	@echo "    [OK] pytz removed"
	@echo ""
	@echo "  [OK] Problem-causing files cleaned up"

	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[PACKAGE] Building distribution artifacts (zip, installer)..."
	@echo "  [ACTION] bash scripts/package/package-all.sh"
	@echo ""
	@echo "Configuration:"
	@echo "  WINDOWS_VERIFY_STRICT: $(WINDOWS_VERIFY_STRICT:-false)"
	@echo ""
	@if [ -n "$(WINDOWS_VERIFY_STRICT)" ] && [ "$(WINDOWS_VERIFY_STRICT)" = "true" ]; then \
		echo "  [INFO] Windows verification in STRICT mode"; \
		echo "       If zip contents differ from source directory, build will fail."; \
	else \
		echo "  [INFO] Windows verification in report-only mode"; \
		echo "       Use WINDOWS_VERIFY_STRICT=true to fail on differences (CI recommended)."; \
	fi
	@echo ""
	WINDOWS_VERIFY_STRICT=$(WINDOWS_VERIFY_STRICT:-false) TAURI_BUILD=$(TAURI_BUILD) bash scripts/package/package-all.sh

	@echo ""
	@echo "---------------------------------------------------------------------------"
	@echo "[VERIFY] Running package verification..."
	@echo "  [ACTION] bash scripts/package/verify-package.sh"
	@echo ""
	@if [ -n "$(PACKAGE_STRICT)" ] && [ "$(PACKAGE_STRICT)" = "true" ]; then \
		echo "  [INFO] Running in STRICT mode (will exit on errors)"; \
		bash scripts/package/verify-package.sh --strict; \
	else \
		echo "  [INFO] Running in report-only mode (use PACKAGE_STRICT=true for strict)"; \
		bash scripts/package/verify-package.sh; \
	fi

	@echo ""
	@echo "==========================================================================="
	@echo "[DONE] Packaging complete!"
	@echo "==========================================================================="
	@echo ""
	@echo "Output location: $(PWD)/dist"
	@ls -lh dist/*.zip dist/*.exe dist/*.dmg 2>/dev/null || echo "  (No artifacts found in dist root)"
	@echo ""

package-pre-check:
	@echo "==========================================================================="
	@echo "Packaging Pre-Check"
	@echo "==========================================================================="
	@echo ""
	@if [ -z "$(SKIP_VENV_CHECK)" ] || [ "$(SKIP_VENV_CHECK)" = "0" ]; then \
		IN_VENV=$$(python3 -c "import sys; print(1 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 0)" 2>/dev/null || echo 0); \
		if [ "$$IN_VENV" != "1" ]; then \
			echo "[ERROR] Not running in a Python virtual environment!"; \
			echo ""; \
			echo "Run these commands first:"; \
			echo "  python3 -m venv .venv"; \
			echo "  source .venv/bin/activate"; \
			echo ""; \
			echo "Or skip this check: SKIP_VENV_CHECK=1 make package"; \
			exit 1; \
		else \
			echo "  [OK] Running in virtual environment"; \
		fi; \
	else \
		echo "  [SKIP] Virtual environment check skipped (SKIP_VENV_CHECK=1)"; \
	fi
	@echo ""
	@if [ ! -d "aw-core" ] || [ ! -f "aw-core/.git" ]; then \
		echo "[ERROR] Submodules not initialized!"; \
		echo ""; \
		echo "Run: git submodule update --init --recursive"; \
		exit 1; \
	else \
		echo "  [OK] Submodules initialized"; \
	fi
	@echo ""
	@echo "Pre-check passed."
	@echo "==========================================================================="

clean:
	rm -rf build dist

# Clean all subprojects
clean_all: clean
	for dir in $(SUBMODULES); do \
		make --directory=$$dir clean; \
	done

clean-auto:
	rm -rIv **/aw-server-rust/target
	rm -rIv **/aw-android/mobile/build
	rm -rIfv **/node_modules
