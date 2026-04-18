#!/bin/bash

set -e

echoerr() { echo "$@" 1>&2; }
log_info() { echo "[INFO] $@"; }
log_error() { echo "[ERROR] $@" 1>&2; }

EXIT_SUCCESS=0
EXIT_VERSION_MISMATCH=10

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TAG_VERSION=""
DISPLAY_VERSION=""

function get_platform() {
    local _platform
    _platform=$(uname | tr '[:upper:]' '[:lower:]')
    if [[ $_platform == "darwin" ]]; then
        _platform="macos"
    elif [[ $_platform == "msys"* ]]; then
        _platform="windows"
    elif [[ $_platform == "mingw"* ]]; then
        _platform="windows"
    elif [[ $_platform == "linux" ]]; then
        true
    else
        echoerr "ERROR: $_platform is not a valid platform"
        exit 1
    fi
    echo "$_platform"
}

function load_version_from_authority() {
    local env_output
    env_output="$("$SCRIPT_DIR/getversion.sh" --env)"
    eval "$env_output"
    
    if [[ -z "$TAG_VERSION" || -z "$DISPLAY_VERSION" ]]; then
        log_error "Failed to load version from authority: $SCRIPT_DIR/getversion.sh"
        exit 1
    fi
}

function verify_version_consistency() {
    local errors=()
    local expected_display="$DISPLAY_VERSION"
    local expected_tag="$TAG_VERSION"
    
    log_info "========================================"
    log_info "VERSION CONSISTENCY CHECK"
    log_info "========================================"
    log_info "Expected DISPLAY_VERSION: $expected_display"
    log_info "Expected TAG_VERSION:     $expected_tag"
    log_info ""
    
    local zip_version=""
    local installer_version=""
    local infoplist_version=""
    
    log_info "Checking zip files in dist/..."
    local zip_file
    zip_file=$(ls dist/activitywatch*.zip 2>/dev/null | head -1 || true)
    if [[ -n "$zip_file" ]]; then
        zip_file=$(basename "$zip_file")
        log_info "  Found zip: $zip_file"
        
        if [[ "$zip_file" =~ activitywatch-([^-]+)- ]]; then
            zip_version="${BASH_REMATCH[1]}"
            log_info "  Extracted version: $zip_version"
        elif [[ "$zip_file" =~ activitywatch-tauri-([^-]+)- ]]; then
            zip_version="${BASH_REMATCH[1]}"
            log_info "  Extracted version: $zip_version"
        fi
        
        if [[ -n "$zip_version" ]]; then
            if [[ "$zip_version" != "$expected_display" ]]; then
                log_error "  ✗ MISMATCH: zip version '$zip_version' != expected '$expected_display'"
                errors+=("zip: '$zip_version'")
            else
                log_info "  ✓ OK: zip version matches"
            fi
        else
            log_info "  ⚠ Could not extract version from zip filename"
        fi
    else
        log_info "  No zip files found (yet)"
    fi
    log_info ""
    
    log_info "Checking installer files in dist/..."
    local installer_file
    installer_file=$(ls dist/activitywatch*-setup.exe 2>/dev/null | head -1 || true)
    if [[ -n "$installer_file" ]]; then
        installer_file=$(basename "$installer_file")
        log_info "  Found installer: $installer_file"
        
        if [[ "$installer_file" =~ activitywatch-([^-]+)- ]]; then
            installer_version="${BASH_REMATCH[1]}"
            log_info "  Extracted version: $installer_version"
        elif [[ "$installer_file" =~ activitywatch-tauri-([^-]+)- ]]; then
            installer_version="${BASH_REMATCH[1]}"
            log_info "  Extracted version: $installer_version"
        fi
        
        if [[ -n "$installer_version" ]]; then
            if [[ "$installer_version" != "$expected_display" ]]; then
                log_error "  ✗ MISMATCH: installer version '$installer_version' != expected '$expected_display'"
                errors+=("installer: '$installer_version'")
            else
                log_info "  ✓ OK: installer version matches"
            fi
        else
            log_info "  ⚠ Could not extract version from installer filename"
        fi
    else
        log_info "  No installer files found (yet)"
    fi
    log_info ""
    
    log_info "Checking Info.plist in dist/ActivityWatch.app/..."
    local infoplist_file="dist/ActivityWatch.app/Contents/Info.plist"
    if [[ -f "$infoplist_file" ]]; then
        log_info "  Found Info.plist: $infoplist_file"
        
        if command -v PlistBuddy &>/dev/null; then
            infoplist_version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$infoplist_file" 2>/dev/null || true)
            log_info "  CFBundleShortVersionString: $infoplist_version"
        elif command -v plutil &>/dev/null; then
            infoplist_version=$(plutil -extract CFBundleShortVersionString xml1 -o - "$infoplist_file" 2>/dev/null | grep -o '<string>[^<]*</string>' | head -1 | sed 's/<[^>]*>//g' || true)
            log_info "  CFBundleShortVersionString: $infoplist_version"
        else
            log_info "  ⚠ No PlistBuddy or plutil found, skipping Info.plist check"
        fi
        
        if [[ -n "$infoplist_version" ]]; then
            if [[ "$infoplist_version" != "$expected_display" ]]; then
                log_error "  ✗ MISMATCH: Info.plist version '$infoplist_version' != expected '$expected_display'"
                errors+=("Info.plist: '$infoplist_version'")
            else
                log_info "  ✓ OK: Info.plist version matches"
            fi
        fi
    else
        log_info "  No Info.plist found (not a macOS Tauri build?)"
    fi
    log_info ""
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        log_error "========================================"
        log_error "VERSION MISMATCH DETECTED!"
        log_error "========================================"
        log_error ""
        log_error "Expected versions (from authority: $SCRIPT_DIR/getversion.sh):"
        log_error "  DISPLAY_VERSION: $expected_display"
        log_error "  TAG_VERSION:     $expected_tag"
        log_error ""
        log_error "Mismatches found:"
        for err in "${errors[@]}"; do
            log_error "  - $err"
        done
        log_error ""
        log_error "All products must use the same DISPLAY_VERSION for:"
        log_error "  - zip filenames"
        log_error "  - installer filenames"
        log_error "  - Info.plist CFBundleShortVersionString"
        log_error ""
        log_error "Expected filename format: activitywatch{,-tauri}-$expected_display-{platform}-{arch}.zip"
        log_error "Expected Info.plist: CFBundleShortVersionString = $expected_display"
        log_error "========================================"
        exit $EXIT_VERSION_MISMATCH
    fi
    
    log_info "✓ All version checks passed"
    log_info "========================================"
}

function get_arch() {
    local _arch
    _arch="$(uname -m)"
    echo "$_arch"
}

function build_zip() {
    log_info "Zipping executables..."
    pushd dist >/dev/null
    local filename
    filename="activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}.zip"
    log_info "  Zip filename: $filename"
    
    if [[ $platform == "windows"* ]]; then
        7z a "$filename" activitywatch
    else
        zip -r "$filename" activitywatch
    fi
    popd >/dev/null
    log_info "  Zip built: dist/$filename"
}

function build_setup() {
    local filename
    filename="activitywatch${build_suffix}-${DISPLAY_VERSION}-${platform}-${arch}-setup.exe"
    log_info "Installer filename: $filename"
    
    local innosetupdir
    innosetupdir="/c/Program Files (x86)/Inno Setup 6"
    if [[ ! -d "$innosetupdir" ]]; then
        log_error "ERROR: Couldn't find innosetup which is needed to build the installer. We suggest you install it using chocolatey. Exiting."
        exit 1
    fi
    
    if [[ $TAURI_BUILD == "true" ]]; then
        env AW_VERSION="$DISPLAY_VERSION" "$innosetupdir/iscc.exe" "$SCRIPT_DIR/aw-tauri.iss"
    else
        env AW_VERSION="$DISPLAY_VERSION" "$innosetupdir/iscc.exe" "$SCRIPT_DIR/activitywatch-setup.iss"
    fi
    mv dist/activitywatch-setup.exe "dist/$filename"
    log_info "  Installer built: dist/$filename"
}

function main() {
    local platform
    local arch
    local build_suffix=""
    
    log_info "========================================"
    log_info "ActivityWatch Packaging Script"
    log_info "========================================"
    log_info ""
    
    log_info "Loading version from authority: $SCRIPT_DIR/getversion.sh"
    load_version_from_authority
    log_info "  TAG_VERSION:     $TAG_VERSION"
    log_info "  DISPLAY_VERSION: $DISPLAY_VERSION"
    log_info ""
    
    platform=$(get_platform)
    arch=$(get_arch)
    
    if [[ $TAURI_BUILD == "true" ]]; then
        build_suffix="-tauri"
    fi
    
    log_info "Build Configuration:"
    log_info "  Platform:       $platform"
    log_info "  Arch:           $arch"
    log_info "  Tauri build:    ${TAURI_BUILD:-false}"
    log_info "  Build suffix:   $build_suffix"
    log_info ""
    
    if [[ $platform == "linux" && $TAURI_BUILD == "true" ]]; then
        log_info "Copying Tauri Linux helper scripts..."
        cp "$SCRIPT_DIR/README.txt" "$SCRIPT_DIR/move-to-aw-modules.sh" dist/activitywatch/
    fi
    log_info ""
    
    log_info "========================================"
    log_info "BUILDING PACKAGES"
    log_info "========================================"
    log_info ""
    
    build_zip
    
    if [[ $platform == "windows"* ]]; then
        log_info ""
        build_setup
    fi
    log_info ""
    
    log_info "========================================"
    log_info "RUNNING CONSISTENCY CHECK"
    log_info "========================================"
    verify_version_consistency
    log_info ""
    
    log_info "========================================"
    log_info "PACKAGE CONTENTS"
    log_info "========================================"
    ls -l dist/activitywatch*.* 2>/dev/null || log_info "  No package files found"
    log_info "========================================"
    
    log_info ""
    log_info "Packaging complete!"
}

main "$@"
