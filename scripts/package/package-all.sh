#!/bin/bash
#
# ActivityWatch Package All Script
# =================================
#
# This script builds distribution artifacts (zip, installer) after the
# initial packaging steps in the Makefile.
#
# Environment Variables:
#   TAURI_BUILD:           Set to "true" for Tauri builds
#   SKIP_WEBUI:            Set to "true" to skip web UI
#   WINDOWS_VERIFY_STRICT: Set to "true" for strict Windows artifact verification
#                           (exits with non-zero code if zip vs source directory differ)
#
# Exit Codes:
#   0:  Success
#   1:  Error (e.g., missing dependencies)
#   2:  Windows verification failed (only with WINDOWS_VERIFY_STRICT=true)
#
# Windows Artifact Consistency:
#   - Source directory: dist/activitywatch/
#   - Zip contents:     activitywatch/ (same structure as source)
#   - Inno Setup input: {#DistDir}\activitywatch\* (same as source)
#   - Installer output: {app}\ (same structure as source)
#   All three should contain the same files for consistency.
#
#   See activitywatch-setup.iss and aw-tauri.iss for Inno Setup source paths.
#   Both use: Source: "{#DistDir}\activitywatch\*"; DestDir: "{app}"; Flags: recursesubdirs
#   This means the installer installs the same files that are in the zip.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =====================================
# Logging Functions
# =====================================

log_info() {
    echo "[INFO] $@"
}

log_action() {
    echo "[ACTION] $@"
}

log_ok() {
    echo "[✓] $@"
}

log_warn() {
    echo "[⚠] $@"
}

log_error() {
    echo "[✗] $@" >&2
}

log_header() {
    echo ""
    echo "========================================"
    echo "$@"
    echo "========================================"
}

log_section() {
    echo ""
    echo "---------------------------------------------------------------------------"
    echo "$@"
    echo "---------------------------------------------------------------------------"
}

# =====================================
# Helper Functions
# =====================================

function get_platform() {
    local _platform
    _platform=$(uname | tr '[:upper:]' '[:lower:]')
    if [[ $_platform == "darwin" ]]; then
        _platform="macos"
    elif [[ $_platform == "msys"* ]] || [[ $_platform == "mingw"* ]]; then
        _platform="windows"
    elif [[ $_platform != "linux" ]]; then
        log_error "Unknown platform: $_platform"
        exit 1
    fi
    echo "$_platform"
}

function get_arch() {
    local _arch
    _arch="$(uname -m)"
    echo "$_arch"
}

# =====================================
# Main
# =====================================

log_header "ActivityWatch Package All"

# Load version from authority
log_section "Loading Version Information"
log_action "Sourcing version from authority: $SCRIPT_DIR/getversion.sh --env"

# Use eval to get TAG_VERSION and DISPLAY_VERSION from the authority
eval "$("$SCRIPT_DIR/getversion.sh" --env)"

log_ok "Version loaded successfully"
log_info "  TAG_VERSION:     $TAG_VERSION"
log_info "  DISPLAY_VERSION: $DISPLAY_VERSION"

# Detect platform and arch
log_section "Detecting Platform"
platform=$(get_platform)
arch=$(get_arch)

# Build suffix for Tauri builds
build_suffix=""
if [[ ${TAURI_BUILD:-false} == "true" ]]; then
    build_suffix="-tauri"
fi

log_ok "Platform detected"
log_info "  Platform:       $platform"
log_info "  Architecture:   $arch"
log_info "  Tauri build:    ${TAURI_BUILD:-false}"
log_info "  Build suffix:   $build_suffix"
log_info ""
log_info "Artifact naming:"
log_info "  Zip:        activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}.zip"
log_info "  Installer:  activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}-setup.exe"

# For Tauri Linux builds, include helper scripts and README
if [[ $platform == "linux" ]] && [[ ${TAURI_BUILD:-false} == "true" ]]; then
    log_section "Copying Tauri Linux Helper Scripts"
    log_action "Copying scripts/package/README.txt → dist/activitywatch/"
    cp "$SCRIPT_DIR/README.txt" dist/activitywatch/
    log_ok "README.txt copied"
    
    log_action "Copying scripts/package/move-to-aw-modules.sh → dist/activitywatch/"
    cp "$SCRIPT_DIR/move-to-aw-modules.sh" dist/activitywatch/
    log_ok "move-to-aw-modules.sh copied"
fi

# =====================================
# Build Zip
# =====================================
log_section "Building Zip Archive"

zip_filename="activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}.zip"

log_info "Zip filename: $zip_filename"
log_action "Entering dist directory"

pushd dist >/dev/null

log_action "Compressing activitywatch/ → $zip_filename"

if [[ $platform == "windows" ]]; then
    log_action "Using 7z for compression (Windows)"
    7z a "$zip_filename" activitywatch
else
    log_action "Using zip for compression (Unix)"
    zip -r "$zip_filename" activitywatch
fi

log_ok "Zip built successfully"
log_info "  File: $zip_filename"
log_info "  Size: $(du -h "$zip_filename" | cut -f1)"

popd >/dev/null

# =====================================
# Build Installer (Windows only)
# =====================================
if [[ $platform == "windows" ]]; then
    log_section "Building Windows Installer"
    
    installer_filename="activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}-setup.exe"
    log_info "Installer filename: $installer_filename"
    
    innosetupdir="/c/Program Files (x86)/Inno Setup 6"
    
    log_action "Checking for Inno Setup"
    if [[ ! -d "$innosetupdir" ]]; then
        log_error "Couldn't find Inno Setup in: $innosetupdir"
        log_info ""
        log_info "Inno Setup is required to build the Windows installer."
        log_info "Install using chocolatey:"
        log_info "  choco install innosetup"
        exit 1
    fi
    log_ok "Inno Setup found: $innosetupdir"
    
    # Windows installer version should NOT include 'v' prefix
    # DISPLAY_VERSION is already without 'v' prefix, so we use it directly
    log_info "Installer version: $DISPLAY_VERSION (no 'v' prefix)"
    
    log_action "Running Inno Setup compiler"
    if [[ ${TAURI_BUILD:-false} == "true" ]]; then
        log_info "  Using Tauri installer script: scripts/package/aw-tauri.iss"
        env AW_VERSION="$DISPLAY_VERSION" "$innosetupdir/iscc.exe" "$SCRIPT_DIR/aw-tauri.iss"
    else
        log_info "  Using standard installer script: scripts/package/activitywatch-setup.iss"
        env AW_VERSION="$DISPLAY_VERSION" "$innosetupdir/iscc.exe" "$SCRIPT_DIR/activitywatch-setup.iss"
    fi
    log_ok "Inno Setup compilation complete"
    
    log_action "Renaming installer: activitywatch-setup.exe → $installer_filename"
    mv dist/activitywatch-setup.exe "dist/$installer_filename"
    log_ok "Installer renamed"
    log_info "  File: $installer_filename"
    log_info "  Size: $(du -h "dist/$installer_filename" | cut -f1)"
    
    # =====================================
    # Windows Artifact Verification
    # =====================================
    log_section "Verifying Windows Artifact Consistency"
    
    log_info "Checking that zip contents match source directory..."
    log_info "  Source: dist/activitywatch/"
    log_info "  Zip:    dist/$zip_filename"
    log_info ""
    log_info "WINDOWS_VERIFY_STRICT: ${WINDOWS_VERIFY_STRICT:-false}"
    log_info ""
    
    # Build arguments for verify script
    VERIFY_ARGS=()
    if [[ ${WINDOWS_VERIFY_STRICT:-false} == "true" ]]; then
        VERIFY_ARGS+=("--strict")
        log_info "  Running in STRICT mode (exits on differences)"
    else
        log_info "  Running in report-only mode (use WINDOWS_VERIFY_STRICT=true to exit on differences)"
    fi
    
    log_action "Calling: $SCRIPT_DIR/verify-windows-artifacts.sh ${VERIFY_ARGS[*]:-}"
    
    # Temporarily disable set -e to capture verification result
    set +e
    
    if [[ ${TAURI_BUILD:-false} == "true" ]]; then
        TAURI_BUILD=true DIST_DIR=./dist "$SCRIPT_DIR/verify-windows-artifacts.sh" "${VERIFY_ARGS[@]}"
    else
        DIST_DIR=./dist "$SCRIPT_DIR/verify-windows-artifacts.sh" "${VERIFY_ARGS[@]}"
    fi
    
    VERIFY_EXIT_CODE=$?
    
    # Re-enable set -e
    set -e
    
    if [[ $VERIFY_EXIT_CODE -eq 0 ]]; then
        log_ok "Windows artifact verification completed successfully"
    elif [[ $VERIFY_EXIT_CODE -eq 2 ]]; then
        log_error "Windows artifact verification found differences (strict mode)"
        log_error "Exiting with non-zero code (WINDOWS_VERIFY_STRICT=true)"
        exit 2
    else
        log_warn "Windows artifact verification completed with non-zero exit code: $VERIFY_EXIT_CODE"
    fi
fi

# =====================================
# List Contents
# =====================================
log_section "Package Contents"

log_info "Listing dist/ directory contents:"
echo ""
ls -lh dist/*.zip dist/*.exe dist/*.dmg 2>/dev/null || log_warn "No artifacts found in dist root"
echo ""

# =====================================
# Summary
# =====================================
log_header "Package All Complete"

log_ok "Artifacts built successfully"
log_info ""
log_info "Summary:"
log_info "  Platform:       $platform"
log_info "  Architecture:   $arch"
log_info "  Version:        $DISPLAY_VERSION"
log_info "  Tauri build:    ${TAURI_BUILD:-false}"
log_info ""
log_info "Artifacts:"
if [[ -f "dist/$zip_filename" ]]; then
    log_info "  ✅ $zip_filename ($(du -h "dist/$zip_filename" | cut -f1))"
fi
if [[ $platform == "windows" ]] && [[ -f "dist/$installer_filename" ]]; then
    log_info "  ✅ $installer_filename ($(du -h "dist/$installer_filename" | cut -f1))"
fi
log_info ""
log_info "Note: Version consistency check will be performed by verify-package.sh"
log_info ""
