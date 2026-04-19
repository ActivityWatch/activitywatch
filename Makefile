# =====================================
# Makefile for the ActivityWatch bundle
# =====================================
#
# [GUIDE] How to install from source:
#  - https://activitywatch.readthedocs.io/en/latest/installing-from-source.html
#
# We recommend creating and activating a Python virtualenv before building.
# Instructions on how to do this can be found in the guide linked above.
.PHONY: build install test clean clean_all

SHELL := /usr/bin/env bash

OS := $(shell uname -s)

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
build: aw-core/.git
#	needed due to https://github.com/pypa/setuptools/issues/1963
#	would ordinarily be specified in pyproject.toml, but is not respected due to https://github.com/pypa/setuptools/issues/1963
	pip install 'setuptools>49.1.1'
	for module in $(SUBMODULES); do \
		echo "Building $$module"; \
		if [ "$$module" = "aw-server-rust" ] && [ "$(TAURI_BUILD)" = "true" ]; then \
			make --directory=$$module aw-sync SKIP_WEBUI=$(SKIP_WEBUI) || { echo "Error in $$module aw-sync"; exit 2; }; \
		else \
			make --directory=$$module build SKIP_WEBUI=$(SKIP_WEBUI) || { echo "Error in $$module build"; exit 2; }; \
		fi; \
	done
#   The below is needed due to: https://github.com/ActivityWatch/activitywatch/issues/173
	make --directory=aw-client build
	make --directory=aw-core build
#	Needed to ensure that the server has the correct version set
	python -c "import aw_server; print(aw_server.__version__)"


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
	# NOTE: This does not codesign the dmg, that is done in the CI config
	pip install dmgbuild
	dmgbuild -s scripts/package/dmgbuild-settings.py -D app=dist/ActivityWatch.app "ActivityWatch" dist/ActivityWatch.dmg

dist/notarize:
	./scripts/notarize.sh

package:
	rm -rf dist
	mkdir -p dist/activitywatch
	for dir in $(PACKAGEABLES); do \
		make --directory=$$dir package; \
		cp -r $$dir/dist/$$dir dist/activitywatch; \
	done
ifeq ($(TAURI_BUILD),true)
# Copy aw-sync binary for Tauri builds
	mkdir -p dist/activitywatch/aw-server-rust
	cp aw-server-rust/target/$(targetdir)/aw-sync dist/activitywatch/aw-server-rust/aw-sync
else
# Move aw-qt to the root of the dist folder
	mv dist/activitywatch/aw-qt aw-qt-tmp
	mv aw-qt-tmp/* dist/activitywatch
	rmdir aw-qt-tmp
endif
# Remove problem-causing binaries
	rm -f dist/activitywatch/libdrm.so.2       # see: https://github.com/ActivityWatch/activitywatch/issues/161
	rm -f dist/activitywatch/libharfbuzz.so.0  # see: https://github.com/ActivityWatch/activitywatch/issues/660#issuecomment-959889230
# These should be provided by the distro itself
# Had to be removed due to otherwise causing the error:
#   aw-qt: symbol lookup error: /opt/activitywatch/libQt5XcbQpa.so.5: undefined symbol: FT_Get_Font_Format
	rm -f dist/activitywatch/libfontconfig.so.1
	rm -f dist/activitywatch/libfreetype.so.6
# Remove unnecessary files
	rm -rf dist/activitywatch/pytz
# Builds zips and setups
	bash scripts/package/package-all.sh

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
