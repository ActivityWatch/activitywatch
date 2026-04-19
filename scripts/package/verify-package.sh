#!/bin/bash
#
# ActivityWatch Package Verification Script
# =========================================
#
# This script verifies the package contents after `make package` completes.
# It checks for:
#   - Critical executables (presence and executability)
#   - Critical directories
#   - Version consistency (across zip, installer, Info.plist)
#
# Usage:
#   bash scripts/package/verify-package.sh          # Print report, exit 0 on success
#   bash scripts/package/verify-package.sh --strict # Exit non-zero on any issue (for CI)
#   bash scripts/package/verify-package.sh --help   # Show help
#
# Environment Variables:
#   DIST_DIR:        Path to dist directory (default: ./dist)
#   EXPECTED_VERSION: Expected version (without v prefix), auto-detected from getversion.sh if not set
#   VERBOSE:         Set to 1 for more detailed output
#
# Exit Codes:
#   0:  All checks passed (or --strict not set and issues found)
#   1:  Critical error (e.g., dist directory not found)
#   2:  Verification failed (only with --strict)
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${DIST_DIR:-./dist}"
EXPECTED_VERSION="${EXPECTED_VERSION:-}"
STRICT_MODE=false
VERBOSE="${VERBOSE:-0}"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
WARNINGS=()
ERRORS=()

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
    WARNINGS+=("$@")
}

log_error() {
    echo "[✗] $@"
    ERRORS+=("$@")
}

log_header() {
    echo ""
    echo "========================================"
    echo "$@"
    echo "========================================"
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Verify ActivityWatch package contents after packaging.

Options:
  --strict        Exit with non-zero code if any check fails (for CI)
  --help, -h      Show this help message

Environment Variables:
  DIST_DIR        Path to dist directory (default: ./dist)
  EXPECTED_VERSION Expected version (auto-detected if not set)
  VERBOSE         Set to 1 for detailed output

Checks performed:
  1. Critical executables (presence + executability)
  2. Critical directories
  3. Version consistency (zip, installer, Info.plist)
EOF
    exit 0
}

# =====================================
# Argument Parsing
# =====================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Unknown argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# =====================================
# Helper Functions
# =====================================

increment_check() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_passed() {
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
}

file_exists() {
    local path="$1"
    increment_check
    if [[ -e "$path" ]]; then
        if [[ $VERBOSE == "1" ]]; then
            log_ok "File exists: $path"
        fi
        check_passed
        return 0
    else
        log_error "File missing: $path"
        return 1
    fi
}

file_executable() {
    local path="$1"
    increment_check
    if [[ -x "$path" ]]; then
        if [[ $VERBOSE == "1" ]]; then
            log_ok "File is executable: $path"
        fi
        check_passed
        return 0
    elif [[ -f "$path" ]]; then
        log_error "File exists but is not executable: $path"
        return 1
    else
        log_error "File missing: $path"
        return 1
    fi
}

dir_exists() {
    local path="$1"
    increment_check
    if [[ -d "$path" ]]; then
        if [[ $VERBOSE == "1" ]]; then
            log_ok "Directory exists: $path"
        fi
        check_passed
        return 0
    else
        log_error "Directory missing: $path"
        return 1
    fi
}

# =====================================
# Version Detection
# =====================================

detect_version() {
    if [[ -z "$EXPECTED_VERSION" ]]; then
        log_info "Auto-detecting version from authority: $SCRIPT_DIR/getversion.sh"
        if [[ -f "$SCRIPT_DIR/getversion.sh" ]]; then
            EXPECTED_VERSION="$("$SCRIPT_DIR/getversion.sh" --display)"
            log_info "  Detected DISPLAY_VERSION: $EXPECTED_VERSION"
        else
            log_error "Cannot detect version: $SCRIPT_DIR/getversion.sh not found"
            exit 1
        fi
    else
        log_info "Using expected version from environment: $EXPECTED_VERSION"
    fi
}

# =====================================
# Check Functions
# =====================================

check_critical_executables() {
    log_header "Checking Critical Executables"
    
    local activitywatch_dir="$DIST_DIR/activitywatch"
    
    if [[ ! -d "$activitywatch_dir" ]]; then
        log_error "ActivityWatch directory not found: $activitywatch_dir"
        return 1
    fi
    
    # aw-server-rust (preferred) or aw-server
    local found_server=false
    if [[ -x "$activitywatch_dir/aw-server-rust/aw-server" ]]; then
        file_executable "$activitywatch_dir/aw-server-rust/aw-server"
        found_server=true
    elif [[ -f "$activitywatch_dir/aw-server-rust/aw-server" ]]; then
        log_error "aw-server-rust/aw-server exists but is not executable"
        increment_check
    elif [[ -x "$activitywatch_dir/aw-server/aw-server" ]]; then
        file_executable "$activitywatch_dir/aw-server/aw-server"
        found_server=true
    elif [[ -f "$activitywatch_dir/aw-server/aw-server" ]]; then
        log_error "aw-server/aw-server exists but is not executable"
        increment_check
    else
        log_error "No server executable found (checked aw-server-rust/aw-server and aw-server/aw-server)"
        increment_check
    fi
    
    # aw-sync (for Tauri builds only - optional)
    if [[ -f "$activitywatch_dir/aw-server-rust/aw-sync" ]] || [[ -f "$activitywatch_dir/aw-sync" ]]; then
        if [[ -x "$activitywatch_dir/aw-server-rust/aw-sync" ]]; then
            file_executable "$activitywatch_dir/aw-server-rust/aw-sync"
        elif [[ -x "$activitywatch_dir/aw-sync" ]]; then
            file_executable "$activitywatch_dir/aw-sync"
        elif [[ -f "$activitywatch_dir/aw-server-rust/aw-sync" ]]; then
            log_error "aw-server-rust/aw-sync exists but is not executable"
            increment_check
        fi
    else
        log_warn "aw-sync not found (expected only in Tauri builds)"
    fi
    
    # aw-watcher-afk
    if [[ -x "$activitywatch_dir/aw-watcher-afk/aw-watcher-afk" ]]; then
        file_executable "$activitywatch_dir/aw-watcher-afk/aw-watcher-afk"
    elif [[ -f "$activitywatch_dir/aw-watcher-afk/aw-watcher-afk" ]]; then
        log_error "aw-watcher-afk exists but is not executable"
        increment_check
    else
        log_warn "aw-watcher-afk not found (may be in development)"
    fi
    
    # aw-watcher-window
    if [[ -x "$activitywatch_dir/aw-watcher-window/aw-watcher-window" ]]; then
        file_executable "$activitywatch_dir/aw-watcher-window/aw-watcher-window"
    elif [[ -f "$activitywatch_dir/aw-watcher-window/aw-watcher-window" ]]; then
        log_error "aw-watcher-window exists but is not executable"
        increment_check
    else
        log_warn "aw-watcher-window not found (may be in development)"
    fi
    
    # aw-qt or aw-tauri (launcher)
    if [[ -x "$activitywatch_dir/aw-qt" ]]; then
        file_executable "$activitywatch_dir/aw-qt"
    elif [[ -f "$activitywatch_dir/aw-qt" ]]; then
        log_error "aw-qt exists but is not executable"
        increment_check
    elif [[ -x "$activitywatch_dir/ActivityWatch.app/Contents/MacOS/ActivityWatch" ]]; then
        # macOS Tauri build
        file_executable "$activitywatch_dir/ActivityWatch.app/Contents/MacOS/ActivityWatch"
    else
        log_warn "No launcher found (aw-qt or ActivityWatch.app)"
    fi
}

check_critical_directories() {
    log_header "Checking Critical Directories"
    
    local activitywatch_dir="$DIST_DIR/activitywatch"
    
    # Main directory
    dir_exists "$activitywatch_dir"
    
    # Check for at least one server directory
    if [[ -d "$activitywatch_dir/aw-server-rust" ]] || [[ -d "$activitywatch_dir/aw-server" ]]; then
        increment_check
        log_ok "Server directory exists (aw-server-rust or aw-server)"
        check_passed
    else
        log_error "No server directory found (aw-server-rust or aw-server)"
    fi
}

check_artifacts() {
    log_header "Checking Distribution Artifacts"
    
    local has_zip=false
    local has_installer=false
    local has_app=false
    
    # Check for zip files
    local zip_files=()
    while IFS= read -r -d '' file; do
        zip_files+=("$file")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "activitywatch*.zip" -print0 2>/dev/null || true)
    
    if [[ ${#zip_files[@]} -gt 0 ]]; then
        has_zip=true
        increment_check
        log_ok "Found ${#zip_files[@]} zip file(s) in $DIST_DIR"
        check_passed
        
        for zip in "${zip_files[@]}"; do
            log_info "  - $(basename "$zip") ($(du -h "$zip" | cut -f1))"
        done
    else
        log_warn "No zip files found in $DIST_DIR"
    fi
    
    # Check for installer (Windows)
    local installer_files=()
    while IFS= read -r -d '' file; do
        installer_files+=("$file")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "*-setup.exe" -print0 2>/dev/null || true)
    
    if [[ ${#installer_files[@]} -gt 0 ]]; then
        has_installer=true
        increment_check
        log_ok "Found ${#installer_files[@]} installer(s) in $DIST_DIR"
        check_passed
        
        for installer in "${installer_files[@]}"; do
            log_info "  - $(basename "$installer") ($(du -h "$installer" | cut -f1))"
        done
    fi
    
    # Check for .app bundle (macOS Tauri)
    if [[ -d "$DIST_DIR/ActivityWatch.app" ]]; then
        has_app=true
        increment_check
        log_ok "Found ActivityWatch.app bundle"
        check_passed
    fi
    
    # Check for dmg (macOS)
    if [[ -f "$DIST_DIR/ActivityWatch.dmg" ]]; then
        increment_check
        log_ok "Found ActivityWatch.dmg ($(du -h "$DIST_DIR/ActivityWatch.dmg" | cut -f1))"
        check_passed
    fi
    
    # Summary
    log_info ""
    if [[ $has_zip == true ]] || [[ $has_installer == true ]] || [[ $has_app == true ]]; then
        log_ok "At least one distribution artifact found"
    else
        log_warn "No distribution artifacts found (zip, installer, or .app)"
    fi
}

check_version_consistency() {
    log_header "Checking Version Consistency"
    
    log_info "Expected version (DISPLAY_VERSION): $EXPECTED_VERSION"
    log_info ""
    
    local mismatches=()
    
    # Check zip file versions
    local zip_files=()
    while IFS= read -r -d '' file; do
        zip_files+=("$file")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "activitywatch*.zip" -print0 2>/dev/null || true)
    
    for zip in "${zip_files[@]}"; do
        local zip_name
        zip_name=$(basename "$zip")
        increment_check
        
        # Expected format: activitywatch{,-tauri}-<version>-<platform>-<arch>.zip
        # Version should be WITHOUT 'v' prefix
        if [[ "$zip_name" =~ activitywatch[^-]*-([^-]+)- ]]; then
            local zip_version="${BASH_REMATCH[1]}"
            if [[ "$zip_version" == "$EXPECTED_VERSION" ]]; then
                log_ok "Zip version matches: $zip_name"
                check_passed
            elif [[ "$zip_version" == "v$EXPECTED_VERSION" ]]; then
                log_error "Zip version has 'v' prefix: expected '$EXPECTED_VERSION', got '$zip_version'"
                mismatches+=("zip '$zip_name' has 'v' prefix: '$zip_version'")
            else
                log_error "Zip version mismatch: expected '$EXPECTED_VERSION', got '$zip_version'"
                mismatches+=("zip '$zip_name': '$zip_version'")
            fi
        else
            log_warn "Could not extract version from zip: $zip_name"
        fi
    done
    
    # Check installer versions
    local installer_files=()
    while IFS= read -r -d '' file; do
        installer_files+=("$file")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "*-setup.exe" -print0 2>/dev/null || true)
    
    for installer in "${installer_files[@]}"; do
        local installer_name
        installer_name=$(basename "$installer")
        increment_check
        
        if [[ "$installer_name" =~ activitywatch[^-]*-([^-]+)- ]]; then
            local installer_version="${BASH_REMATCH[1]}"
            if [[ "$installer_version" == "$EXPECTED_VERSION" ]]; then
                log_ok "Installer version matches: $installer_name"
                check_passed
            elif [[ "$installer_version" == "v$EXPECTED_VERSION" ]]; then
                log_error "Installer version has 'v' prefix: expected '$EXPECTED_VERSION', got '$installer_version'"
                mismatches+=("installer '$installer_name' has 'v' prefix: '$installer_version'")
            else
                log_error "Installer version mismatch: expected '$EXPECTED_VERSION', got '$installer_version'"
                mismatches+=("installer '$installer_name': '$installer_version'")
            fi
        else
            log_warn "Could not extract version from installer: $installer_name"
        fi
    done
    
    # Check Info.plist version (macOS)
    local infoplist="$DIST_DIR/ActivityWatch.app/Contents/Info.plist"
    if [[ -f "$infoplist" ]]; then
        increment_check
        local infoplist_version=""
        
        if command -v PlistBuddy &>/dev/null; then
            infoplist_version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$infoplist" 2>/dev/null || true)
        elif command -v plutil &>/dev/null; then
            infoplist_version=$(plutil -extract CFBundleShortVersionString xml1 -o - "$infoplist" 2>/dev/null | grep -o '<string>[^<]*</string>' | head -1 | sed 's/<[^>]*>//g' || true)
        fi
        
        if [[ -n "$infoplist_version" ]]; then
            if [[ "$infoplist_version" == "$EXPECTED_VERSION" ]]; then
                log_ok "Info.plist version matches: $infoplist_version"
                check_passed
            elif [[ "$infoplist_version" == "v$EXPECTED_VERSION" ]]; then
                log_error "Info.plist version has 'v' prefix: expected '$EXPECTED_VERSION', got '$infoplist_version'"
                mismatches+=("Info.plist has 'v' prefix: '$infoplist_version'")
            else
                log_error "Info.plist version mismatch: expected '$EXPECTED_VERSION', got '$infoplist_version'"
                mismatches+=("Info.plist: '$infoplist_version'")
            fi
        else
            log_warn "Could not read Info.plist version"
        fi
    fi
    
    # Summary
    log_info ""
    if [[ ${#mismatches[@]} -gt 0 ]]; then
        log_error "========================================"
        log_error "VERSION MISMATCHES FOUND"
        log_error "========================================"
        log_error "Expected version: $EXPECTED_VERSION"
        log_error ""
        for mismatch in "${mismatches[@]}"; do
            log_error "  - $mismatch"
        done
        log_error "========================================"
    else
        log_ok "All version checks passed"
    fi
}

# =====================================
# Main
# =====================================

main() {
    log_header "ActivityWatch Package Verification"
    
    # Check dist directory
    if [[ ! -d "$DIST_DIR" ]]; then
        log_error "Dist directory not found: $DIST_DIR"
        log_error "Run 'make package' first to create the dist directory."
        exit 1
    fi
    
    log_info "Dist directory: $DIST_DIR"
    log_info "Strict mode: $STRICT_MODE"
    log_info ""
    
    # Detect version
    detect_version
    
    # Run checks
    check_critical_executables
    check_critical_directories
    check_artifacts
    check_version_consistency
    
    # Print summary
    log_header "Verification Summary"
    log_info "Total checks:  $TOTAL_CHECKS"
    log_info "Passed:        $PASSED_CHECKS"
    log_info "Warnings:      ${#WARNINGS[@]}"
    log_info "Errors:        ${#ERRORS[@]}"
    log_info ""
    
    if [[ ${#ERRORS[@]} -gt 0 ]]; then
        log_info "Errors encountered:"
        for err in "${ERRORS[@]}"; do
            log_info "  - $err"
        done
        log_info ""
    fi
    
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        log_info "Warnings encountered:"
        for warn in "${WARNINGS[@]}"; do
            log_info "  - $warn"
        done
        log_info ""
    fi
    
    # Determine exit code
    if [[ $STRICT_MODE == true ]] && [[ ${#ERRORS[@]} -gt 0 ]]; then
        log_header "FINAL RESULT: FAILED (--strict mode)"
        log_error "Verification failed with ${#ERRORS[@]} error(s) and ${#WARNINGS[@]} warning(s)"
        log_info "Use without --strict to see report only"
        exit 2
    elif [[ ${#ERRORS[@]} -gt 0 ]]; then
        log_header "FINAL RESULT: ISSUES FOUND (not --strict)"
        log_warn "Verification found ${#ERRORS[@]} error(s) and ${#WARNINGS[@]} warning(s)"
        log_info "Use --strict to exit with non-zero code"
        exit 0
    else
        log_header "FINAL RESULT: PASSED"
        log_ok "All ${PASSED_CHECKS}/${TOTAL_CHECKS} checks passed (${#WARNINGS[@]} warnings)"
        exit 0
    fi
}

main "$@"
