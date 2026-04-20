#!/bin/bash
#
# ActivityWatch macOS Signing Script
# ==================================
#
# This script performs "inside-out" code signing for macOS .app bundles.
# Signing order: frameworks/bundles → dylibs/so → executables → .app bundle
#
# Environment Variables:
#   AW_IDENTITY:       Code signing identity (e.g., "Developer ID Application: ...")
#                      Falls back to APPLE_PERSONALID if not set.
#   AW_ENTITLEMENTS:   Path to entitlements.plist (default: scripts/package/entitlements.plist)
#   AW_VERBOSE:        Set to "1" for verbose output
#   AW_DRY_RUN:         Set to "1" to show commands without executing
#
# Usage:
#   bash scripts/package/sign-macos.sh dist/ActivityWatch.app
#   bash scripts/package/sign-macos.sh dist/ActivityWatch.dmg
#
# Exit Codes:
#   0:  Success
#   1:  Error
#   2:  Help shown
#

set -euo pipefail

# =====================================
# Configuration
# =====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ENTITLEMENTS="$SCRIPT_DIR/entitlements.plist"

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

log_error() {
    echo "[✗] $@" >&2
}

log_debug() {
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        echo "[DEBUG] $@"
    fi
}

log_command() {
    echo "[CMD] $@"
}

# =====================================
# Helper Functions
# =====================================

show_help() {
    cat << EOF
ActivityWatch macOS Signing Script

Usage: $(basename "$0") [OPTIONS] <path-to-app-or-dmg>

Signs a macOS .app bundle or .dmg file with "inside-out" order:
  1. Framework/bundle directories (.framework, .bundle, .plugin)
  2. Mach-O binary files (dylibs, .so files)
  3. Top-level .app bundle

Environment Variables:
  AW_IDENTITY       Code signing identity (e.g., "Developer ID Application: ...")
                    Falls back to APPLE_PERSONALID if not set.
  AW_ENTITLEMENTS   Path to entitlements.plist
                    (default: scripts/package/entitlements.plist)
  AW_VERBOSE        Enable verbose output ("1")
  AW_DRY_RUN         Show commands without executing ("1")

Examples:
  # Sign an app bundle
  AW_IDENTITY="Developer ID Application: My Name (ABC123)" \\
    bash scripts/package/sign-macos.sh dist/ActivityWatch.app

  # Sign a DMG
  AW_IDENTITY="Developer ID Application: My Name (ABC123)" \\
    bash scripts/package/sign-macos.sh dist/ActivityWatch.dmg

Troubleshooting Commands (run manually to diagnose):
  # List available signing identities
  security find-identity -v -p codesigning

  # Verify code signature
  codesign -v --verify --strict dist/ActivityWatch.app

  # Show detailed signature info
  codesign -dvvv dist/ActivityWatch.app

  # Run Gatekeeper assessment
  spctl -a -vvv -t execute dist/ActivityWatch.app
EOF
    exit 2
}

# Run a command, optionally showing it first
run_cmd() {
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command "$@"
        return 0
    fi
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        log_command "$@"
    fi
    "$@"
}

# Check if a file is a Mach-O binary
is_macho() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    local file_type
    file_type=$(file "$file" 2>/dev/null)
    if echo "$file_type" | grep -q "Mach-O"; then
        return 0
    fi
    return 1
}

# =====================================
# Signing Functions
# =====================================

# Sign a single binary or directory
sign_item() {
    local item="$1"
    local identity="$2"
    local entitlements="$3"
    
    log_action "Signing: $item"
    
    # Build codesign arguments
    local args=("--force" "--options" "runtime" "--timestamp")
    
    if [[ -n "$entitlements" ]] && [[ -f "$entitlements" ]]; then
        args+=("--entitlements" "$entitlements")
    fi
    
    args+=("--sign" "$identity")
    args+=("$item")
    
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        args+=("--verbose")
    fi
    
    run_cmd codesign "${args[@]}"
}

# Sign Mach-O binaries (inside-out order)
sign_binaries() {
    local app_path="$1"
    local identity="$2"
    local entitlements="$3"
    
    log_info "Phase 1: Signing Mach-O binary files (dylibs, .so, executables)"
    
    # Find all Mach-O files, sort by path length descending (inside-out)
    # Skip files inside bundle directories (.framework, .bundle, .plugin)
    # - those are signed in sign_bundles() to avoid "bundle format is ambiguous" errors
    
    local binaries=()
    while IFS= read -r -d '' file; do
        # Skip if file doesn't exist
        [[ ! -f "$file" ]] && continue
        
        # Skip symlinks
        [[ -L "$file" ]] && continue
        
        # Check if it's a Mach-O binary
        if is_macho "$file"; then
            # Check if parent is a bundle directory
            local parent
            parent=$(dirname "$file")
            local is_inside_bundle=false
            
            # Check if any ancestor is a bundle (.framework, .bundle, .plugin)
            local current="$parent"
            while [[ "$current" != "/" ]] && [[ "$current" != "." ]]; do
                if [[ "$current" == *.framework ]] || \
                   [[ "$current" == *.bundle ]] || \
                   [[ "$current" == *.plugin ]]; then
                    is_inside_bundle=true
                    break
                fi
                current=$(dirname "$current")
            done
            
            if [[ "$is_inside_bundle" == "true" ]]; then
                log_debug "Skipping bundle binary (signed separately): $file"
                continue
            fi
            
            binaries+=("$file")
        fi
    done < <(find "$app_path" -type f -print0 2>/dev/null)
    
    # Sort by path length descending (inside-out)
    if [[ ${#binaries[@]} -gt 0 ]]; then
        # Create a temporary file for sorting
        local tmp_sort
        tmp_sort=$(mktemp)
        for bin in "${binaries[@]}"; do
            local len=${#bin}
            echo "$len $bin" >> "$tmp_sort"
        done
        
        # Sort and sign
        while IFS= read -r line; do
            local bin
            bin=$(echo "$line" | cut -d' ' -f2-)
            sign_item "$bin" "$identity" "$entitlements"
        done < <(sort -rn "$tmp_sort")
        
        rm -f "$tmp_sort"
        log_ok "Signed ${#binaries[@]} binary files"
    else
        log_info "No standalone binary files found"
    fi
}

# Sign bundle directories (.framework, .bundle, .plugin)
sign_bundles() {
    local app_path="$1"
    local identity="$2"
    local entitlements="$3"
    
    log_info "Phase 2: Signing bundle directories (.framework, .bundle, .plugin)"
    
    # Find all bundle directories, sort by path length descending (inside-out)
    local bundles=()
    while IFS= read -r -d '' bundle; do
        # Skip if not a directory
        [[ ! -d "$bundle" ]] && continue
        
        # Skip if inside another bundle (we handle this via sorting)
        bundles+=("$bundle")
    done < <(find "$app_path" -type d \( \
        -name "*.framework" -o \
        -name "*.bundle" -o \
        -name "*.plugin" \
    \) -print0 2>/dev/null)
    
    if [[ ${#bundles[@]} -gt 0 ]]; then
        # Sort by path length descending (inside-out)
        local tmp_sort
        tmp_sort=$(mktemp)
        for bundle in "${bundles[@]}"; do
            local len=${#bundle}
            echo "$len $bundle" >> "$tmp_sort"
        done
        
        # Sort and sign
        local signed_count=0
        while IFS= read -r line; do
            local bundle
            bundle=$(echo "$line" | cut -d' ' -f2-)
            
            # Try signing the bundle directly
            log_action "Signing bundle: $bundle"
            
            local sign_output
            sign_output=$(sign_item "$bundle" "$identity" "$entitlements" 2>&1) || {
                # Check if error is "bundle format is ambiguous"
                if echo "$sign_output" | grep -qi "bundle format is ambiguous"; then
                    log_debug "Bundle has ambiguous format, trying alternative approach: $bundle"
                    log_debug "This usually means the bundle lacks standard structure (e.g., PyInstaller frameworks)"
                    
                    # For ambiguous bundles, sign the Mach-O files inside directly
                    local inner_binaries=()
                    while IFS= read -r -d '' inner; do
                        if is_macho "$inner" && [[ ! -L "$inner" ]]; then
                            inner_binaries+=("$inner")
                        fi
                    done < <(find "$bundle" -type f -print0 2>/dev/null)
                    
                    for inner in "${inner_binaries[@]}"; do
                        sign_item "$inner" "$identity" "$entitlements"
                    done
                    
                    log_ok "Signed ${#inner_binaries[@]} binaries inside ambiguous bundle: $bundle"
                else
                    log_error "Failed to sign bundle: $bundle"
                    log_error "$sign_output"
                    return 1
                fi
            }
            ((signed_count++))
        done < <(sort -rn "$tmp_sort")
        
        rm -f "$tmp_sort"
        log_ok "Signed $signed_count bundle directories"
    else
        log_info "No bundle directories found"
    fi
}

# Sign the top-level .app bundle
sign_app_top_level() {
    local app_path="$1"
    local identity="$2"
    local entitlements="$3"
    
    log_info "Phase 3: Signing top-level .app bundle"
    sign_item "$app_path" "$identity" "$entitlements"
    log_ok "Top-level .app bundle signed"
}

# =====================================
# Validation Functions
# =====================================

# Show troubleshooting commands
show_troubleshooting_commands() {
    local target="$1"
    log_info ""
    log_info "================================================================="
    log_info "Troubleshooting Commands (copy/paste to diagnose issues)"
    log_info "================================================================="
    log_info ""
    log_info "# List available signing identities:"
    log_info "  security find-identity -v -p codesigning"
    log_info ""
    log_info "# Verify code signature:"
    log_info "  codesign -v --verify --strict '$target'"
    log_info ""
    log_info "# Show detailed signature information:"
    log_info "  codesign -dvvv '$target'"
    log_info ""
    log_info "# Run Gatekeeper assessment:"
    log_info "  spctl -a -vvv -t execute '$target'"
    log_info ""
    log_info "# Check signature status recursively:"
    log_info "  codesign -v --verify --strict --deep '$target'"
    log_info ""
    log_info "================================================================="
}

# Validate the signature
validate_signature() {
    local target="$1"
    
    log_info "Validating signature..."
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_info "[DRY-RUN] Skipping validation in dry-run mode"
        return 0
    fi
    
    # Basic verification
    log_action "Running: codesign -v --verify --strict '$target'"
    if codesign -v --verify --strict "$target" 2>&1; then
        log_ok "Basic signature validation passed"
    else
        log_error "Signature validation FAILED"
        show_troubleshooting_commands "$target"
        return 1
    fi
    
    # Show signature info (verbose mode only)
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        log_debug "Signature details:"
        codesign -dvvv "$target" 2>&1 || true
    fi
    
    log_ok "Signature validated successfully"
    return 0
}

# =====================================
# Main
# =====================================

main() {
    # Parse arguments
    if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        show_help
    fi
    
    local target="$1"
    
    # Check if target exists
    if [[ ! -e "$target" ]]; then
        log_error "Target not found: $target"
        exit 1
    fi
    
    # Determine signing identity
    local identity="${AW_IDENTITY:-}"
    if [[ -z "$identity" ]]; then
        identity="${APPLE_PERSONALID:-}"
    fi
    
    if [[ -z "$identity" ]]; then
        log_error "No signing identity specified"
        log_info ""
        log_info "Set AW_IDENTITY or APPLE_PERSONALID environment variable."
        log_info "Example:"
        log_info "  AW_IDENTITY=\"Developer ID Application: Your Name (ABC123)\" \\\""
        log_info "    bash $0 $target"
        log_info ""
        log_info "Use this command to list available identities:"
        log_info "  security find-identity -v -p codesigning"
        exit 1
    fi
    
    # Determine entitlements file
    local entitlements="${AW_ENTITLEMENTS:-}"
    if [[ -z "$entitlements" ]] || [[ ! -f "$entitlements" ]]; then
        if [[ -f "$DEFAULT_ENTITLEMENTS" ]]; then
            entitlements="$DEFAULT_ENTITLEMENTS"
        else
            entitlements=""
        fi
    fi
    
    log_info "================================================================="
    log_info "ActivityWatch macOS Signing"
    log_info "================================================================="
    log_info ""
    log_info "Configuration:"
    log_info "  Target:         $target"
    log_info "  Identity:       $identity"
    if [[ -n "$entitlements" ]]; then
        log_info "  Entitlements:   $entitlements"
    fi
    log_info "  Dry run:        ${AW_DRY_RUN:-0}"
    log_info "  Verbose:        ${AW_VERBOSE:-0}"
    log_info ""
    
    # Check what we're signing
    if [[ "$target" == *.dmg ]]; then
        log_info "Signing DMG file"
        # DMG is signed directly (no inside-out needed)
        sign_item "$target" "$identity" "$entitlements"
    elif [[ "$target" == *.app ]]; then
        log_info "Signing .app bundle (inside-out order)"
        log_info ""
        
        # Inside-out signing order
        sign_bundles "$target" "$identity" "$entitlements"
        sign_binaries "$target" "$identity" "$entitlements"
        sign_app_top_level "$target" "$identity" "$entitlements"
    else
        # Try to detect type
        if [[ -d "$target" ]]; then
            log_info "Signing directory (inside-out order)"
            log_info ""
            sign_bundles "$target" "$identity" "$entitlements"
            sign_binaries "$target" "$identity" "$entitlements"
        else
            log_info "Signing single file"
            sign_item "$target" "$identity" "$entitlements"
        fi
    fi
    
    log_info ""
    log_info "================================================================="
    log_info "Signing Complete"
    log_info "================================================================="
    log_info ""
    
    # Validate signature
    validate_signature "$target"
    
    # Show troubleshooting commands
    show_troubleshooting_commands "$target"
    
    log_ok "All done!"
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
