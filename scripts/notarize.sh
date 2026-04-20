#!/bin/bash
#
# ActivityWatch macOS Notarization Script
# =====================================
#
# This script handles macOS code signing and notarization for ActivityWatch.
#
# Environment Variables:
#   ====================== Signing ======================
#   AW_SIGN:           Set to "true" to enable code signing before notarization
#   AW_IDENTITY:       Code signing identity (e.g., "Developer ID Application: ...")
#                         Falls back to APPLE_PERSONALID if not set.
#   AW_ENTITLEMENTS:   Path to entitlements.plist (default: scripts/package/entitlements.plist)
#
#   ====================== Notarization ======================
#   AW_NOTARIZE:       Set to "true" to enable notarization
#   APPLE_EMAIL:       Apple ID email
#   APPLE_PASSWORD:    App-specific password
#   APPLE_TEAMID:      Apple Developer Team ID
#   APPLE_PERSONALID:  Developer ID identity (for fallback identity)
#
#   ====================== Other ======================
#   AW_DRY_RUN:        Show commands without executing
#   AW_VERBOSE:        Verbose output
#   AW_KEYCHAIN_PROFILE:  Keychain profile name (default: activitywatch-notarization)
#   AW_BUNDLE_ID:      Bundle ID (default: net.activitywatch.ActivityWatch)
#
# Usage:
#   # Sign only:
#     AW_SIGN=true AW_IDENTITY="Developer ID Application: ..." ./scripts/notarize.sh
#
#   # Notarize only (already signed):
#     AW_NOTARIZE=true APPLE_EMAIL=... ./scripts/notarize.sh
#
#   # Sign AND notarize:
#     AW_SIGN=true AW_NOTARIZE=true AW_IDENTITY="..." APPLE_EMAIL=... ./scripts/notarize.sh
#
#   # Dry run (show commands only):
#     AW_DRY_RUN=true AW_SIGN=true AW_NOTARIZE=true ./scripts/notarize.sh
#
# Exit Codes:
#   0:  Success
#   1:  General error
#   2:  Missing credentials
#   3:  Missing tools
#   4:  Notarization failed
#   5:  Signing failed
#   6:  Help shown
#

set -euo pipefail

# =====================================
# Constants
# =====================================

EXIT_SUCCESS=0
EXIT_ERROR=1
EXIT_MISSING_CREDENTIALS=2
EXIT_MISSING_TOOLS=3
EXIT_NOTARIZATION_FAILED=4
EXIT_SIGNING_FAILED=5
EXIT_HELP=6

# =====================================
# Configuration
# =====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
BUNDLE_ID="${AW_BUNDLE_ID:-net.activitywatch.ActivityWatch}"
KEYCHAIN_PROFILE="${AW_KEYCHAIN_PROFILE:-activitywatch-notarization}"
APP_PATH="${AW_APP_PATH:-$PROJECT_ROOT/dist/ActivityWatch.app}"
DMG_PATH="${AW_DMG_PATH:-$PROJECT_ROOT/dist/ActivityWatch.dmg}"

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
    echo "[OK] $@"
}

log_error() {
    echo "[ERROR] $@" >&2
}

log_warn() {
    echo "[WARN] $@"
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
ActivityWatch macOS Notarization Script

Signs and/or notarizes macOS .app bundles and .dmg files.

Environment Variables:
  ============= Signing =============
  AW_SIGN=true           Enable code signing
  AW_IDENTITY            Signing identity (e.g., "Developer ID Application: ...")
  AW_ENTITLEMENTS        Path to entitlements.plist

  ============= Notarization =============
  AW_NOTARIZE=true       Enable notarization
  APPLE_EMAIL            Apple ID email
  APPLE_PASSWORD         App-specific password
  APPLE_TEAMID           Team ID
  APPLE_PERSONALID       Developer ID (for fallback identity)

  ============= Other =============
  AW_DRY_RUN=true        Show commands without executing
  AW_VERBOSE=true        Verbose output
  AW_APP_PATH            Path to .app (default: dist/ActivityWatch.app)
  AW_DMG_PATH            Path to .dmg (default: dist/ActivityWatch.dmg)
  AW_BUNDLE_ID           Bundle ID (default: net.activitywatch.ActivityWatch)

Usage:
  # Sign only:
    AW_SIGN=true AW_IDENTITY="Developer ID Application: ..." ./scripts/notarize.sh

  # Notarize only:
    AW_NOTARIZE=true APPLE_EMAIL=... ./scripts/notarize.sh

  # Sign AND notarize:
    AW_SIGN=true AW_NOTARIZE=true AW_IDENTITY="..." APPLE_EMAIL=... ./scripts/notarize.sh

Troubleshooting Commands:
  # List signing identities
  security find-identity -v -p codesigning

  # Verify signature
  codesign -v --verify --strict dist/ActivityWatch.app

  # Check notarization history
  xcrun notarytool history --keychain-profile $KEYCHAIN_PROFILE

  # Check stapler validation
  xcrun stapler validate dist/ActivityWatch.app
EOF
    exit $EXIT_HELP
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

# Show troubleshooting commands for a given submission
show_troubleshooting() {
    local submission_uuid="${1:-}"
    log_info ""
    log_info "================================================================="
    log_info "Troubleshooting Commands"
    log_info "================================================================="
    log_info ""
    log_info "# === Signing ==="
    log_info ""
    log_info "  # List available identities:"
    log_info "    security find-identity -v -p codesigning"
    log_info ""
    log_info "  # Verify signature on app:"
    log_info "    codesign -v --verify --strict \"$APP_PATH\""
    log_info ""
    log_info "  # Verify signature on dmg:"
    log_info "    codesign -v --verify --strict \"$DMG_PATH\""
    log_info ""
    log_info "  # Show signature details:"
    log_info "    codesign -dvvv \"$APP_PATH\""
    log_info ""
    log_info "  # Run Gatekeeper assessment:"
    log_info "    spctl -a -vvv -t execute \"$APP_PATH\""
    log_info ""
    log_info "# === Notarization ==="
    log_info ""
    log_info "  # Check notarization history:"
    log_info "    xcrun notarytool history --keychain-profile $KEYCHAIN_PROFILE"
    log_info ""
    if [[ -n "$submission_uuid" ]]; then
        log_info "  # Get detailed logs for submission $submission_uuid:"
        log_info "    xcrun notarytool log \"$submission_uuid\" --keychain-profile $KEYCHAIN_PROFILE"
        log_info ""
        log_info "  # Get submission info:"
        log_info "    xcrun notarytool info \"$submission_uuid\" --keychain-profile $KEYCHAIN_PROFILE"
        log_info ""
    fi
    log_info "  # Check stapler validation:"
    log_info "    xcrun stapler validate \"$APP_PATH\""
    log_info "    xcrun stapler validate \"$DMG_PATH\""
    log_info ""
    log_info "================================================================="
}

# =====================================
# Tool Detection
# =====================================

# Check if a tool is available
has_tool() {
    local tool="$1"
    if command -v "$tool" >/dev/null 2>&1; then
        return 0
    fi
    # Also check via xcrun for Apple developer tools
    if xcrun -f "$tool" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Detect notarization tools
detect_tools() {
    log_info "Detecting notarization tools..."
    
    local has_notarytool=false
    local has_altool=false
    local has_stapler=false
    
    # Check notarytool (Xcode >= 13)
    if has_tool xcrun; then
        if xcrun notarytool --help >/dev/null 2>&1; then
            has_notarytool=true
            log_ok "  notarytool (Xcode >= 13) - PREFERRED"
        fi
    fi
    
    # Check altool (Xcode < 13)
    if has_tool xcrun; then
        if xcrun altool --help >/dev/null 2>&1; then
            has_altool=true
            log_ok "  altool (Xcode < 13) - FALLBACK"
        fi
    fi
    
    # Check stapler
    if has_tool xcrun; then
        if xcrun stapler --help >/dev/null 2>&1; then
            has_stapler=true
            log_ok "  stapler"
        fi
    fi
    
    if [[ "$has_notarytool" == "false" && "$has_altool" == "false" ]]; then
        log_error "No notarization tools found."
        log_info ""
        log_info "Please install Xcode command line tools or full Xcode."
        log_info "Xcode 13+ includes notarytool (preferred)."
        log_info "Older Xcode versions use altool."
        return 1
    fi
    
    if [[ "$has_stapler" == "false" ]]; then
        log_error "stapler not found (required for stapling)."
        return 1
    fi
    
    # Set method: prefer notarytool over altool
    if [[ "$has_notarytool" == "true" ]]; then
        NOTARIZATION_METHOD="notarytool"
    else
        NOTARIZATION_METHOD="altool"
    fi
    
    log_info ""
    log_info "Selected method: $NOTARIZATION_METHOD"
    
    return 0
}

# =====================================
# Credential Validation
# =====================================

validate_signing_credentials() {
    log_info "Validating signing credentials..."
    
    local identity="${AW_IDENTITY:-}"
    if [[ -z "$identity" ]]; then
        identity="${APPLE_PERSONALID:-}"
    fi
    
    if [[ -z "$identity" ]]; then
        log_error "Missing signing identity."
        log_info ""
        log_info "Set AW_IDENTITY or APPLE_PERSONALID environment variable."
        log_info ""
        log_info "Example:"
        log_info "  export AW_IDENTITY=\"Developer ID Application: Your Name (ABC123)\""
        log_info ""
        log_info "List available identities:"
        log_info "  security find-identity -v -p codesigning"
        return 1
    fi
    
    # Store for later use
    SIGNING_IDENTITY="$identity"
    
    log_ok "Signing identity: $identity"
    return 0
}

validate_notarization_credentials() {
    log_info "Validating notarization credentials..."
    
    local missing=()
    
    if [[ -z "${APPLE_EMAIL:-}" ]]; then
        missing+=("APPLE_EMAIL")
    fi
    if [[ -z "${APPLE_PASSWORD:-}" ]]; then
        missing+=("APPLE_PASSWORD")
    fi
    if [[ -z "${APPLE_TEAMID:-}" ]]; then
        missing+=("APPLE_TEAMID")
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing[@]}"; do
            log_error "  - $var"
        done
        log_info ""
        log_info "Example configuration:"
        log_info "  export APPLE_EMAIL=\"your-apple-id@example.com\""
        log_info "  export APPLE_PASSWORD=\"xxxx-xxxx-xxxx-xxxx\"  # App-specific password"
        log_info "  export APPLE_TEAMID=\"XXXXXXXXXX\"             # Team ID"
        log_info ""
        log_info "  # Get app-specific password:"
        log_info "  https://appleid.apple.com/account/manage"
        return 1
    fi
    
    log_ok "All notarization credentials configured."
    log_debug "  APPLE_EMAIL:    $(if [[ -n "${APPLE_EMAIL:-}" ]]; then echo "set"; else echo "not set"; fi)"
    log_debug "  APPLE_PASSWORD: $(if [[ -n "${APPLE_PASSWORD:-}" ]]; then echo "set"; else echo "not set"; fi)"
    log_debug "  APPLE_TEAMID:   $(if [[ -n "${APPLE_TEAMID:-}" ]]; then echo "set"; else echo "not set"; fi)"
    
    return 0
}

# =====================================
# Signing Functions
# =====================================

sign_app() {
    log_info ""
    log_info "========================================"
    log_info "Signing .app Bundle"
    log_info "========================================"
    log_info ""
    
    if [[ ! -d "$APP_PATH" ]]; then
        log_error ".app not found: $APP_PATH"
        log_info "Expected: $APP_PATH"
        return $EXIT_SIGNING_FAILED
    fi
    
    log_info "Signing: $APP_PATH"
    log_info "Identity: $SIGNING_IDENTITY"
    
    # Use sign-macos.sh script for inside-out signing
    local sign_script="$SCRIPT_DIR/package/sign-macos.sh"
    if [[ ! -f "$sign_script" ]]; then
        sign_script="$SCRIPT_DIR/sign-macos.sh"
    fi
    
    if [[ ! -f "$sign_script" ]]; then
        log_error "sign-macos.sh not found. Looked in:"
        log_error "  $SCRIPT_DIR/package/sign-macos.sh"
        log_error "  $SCRIPT_DIR/sign-macos.sh"
        return $EXIT_SIGNING_FAILED
    fi
    
    # Build environment for sign-macos.sh
    local sign_env=()
    sign_env+=("AW_IDENTITY=$SIGNING_IDENTITY")
    if [[ -n "${AW_ENTITLEMENTS:-}" ]]; then
        sign_env+=("AW_ENTITLEMENTS=$AW_ENTITLEMENTS")
    fi
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        sign_env+=("AW_VERBOSE=1")
    fi
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        sign_env+=("AW_DRY_RUN=1")
    fi
    
    log_action "Calling: ${sign_env[*]} $sign_script $APP_PATH"
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command env "${sign_env[@]}" bash "$sign_script" "$APP_PATH"
    else
        env "${sign_env[@]}" bash "$sign_script" "$APP_PATH"
    fi
    
    log_ok ".app signing complete."
}

sign_dmg() {
    log_info ""
    log_info "========================================"
    log_info "Signing DMG"
    log_info "========================================"
    log_info ""
    
    if [[ ! -f "$DMG_PATH" ]]; then
        log_warn "DMG not found: $DMG_PATH"
        log_info "Skipping DMG signing (this is OK if you're only signing the .app)."
        return 0
    fi
    
    log_info "Signing: $DMG_PATH"
    log_info "Identity: $SIGNING_IDENTITY"
    
    # Build codesign arguments
    local args=("--force" "--timestamp" "--sign" "$SIGNING_IDENTITY" "$DMG_PATH")
    
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        args+=("--verbose")
    fi
    
    log_action "codesign ${args[*]} $DMG_PATH"
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command codesign "${args[@]}"
    else
        codesign "${args[@]}"
    fi
    
    log_ok "DMG signing complete."
}

# =====================================
# Notarization Functions
# =====================================

# Store credentials in keychain
store_credentials() {
    log_info "Storing credentials in keychain..."
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command "xcrun notarytool store-credentials $KEYCHAIN_PROFILE --apple-id APPLE_EMAIL --team-id APPLE_TEAMID --password APPLE_PASSWORD"
        log_info "[DRY-RUN] Skipping actual credential storage."
        return 0
    fi
    
    if [[ "$NOTARIZATION_METHOD" == "notarytool" ]]; then
        xcrun notarytool store-credentials "$KEYCHAIN_PROFILE" \
            --apple-id "$APPLE_EMAIL" \
            --team-id "$APPLE_TEAMID" \
            --password "$APPLE_PASSWORD"
    else
        xcrun altool --store-password-in-keychain-item "$KEYCHAIN_PROFILE" \
            -u "$APPLE_EMAIL" \
            -p "$APPLE_PASSWORD"
    fi
}

# Submit to Apple for notarization using notarytool
submit_notarytool() {
    local dist_path="$1"
    
    log_info "Submitting to Apple for notarization (notarytool)..."
    log_info "  File: $dist_path"
    
    # Build arguments
    local args=("submit" "$dist_path" "--keychain-profile" "$KEYCHAIN_PROFILE" "--wait")
    
    if [[ "${AW_VERBOSE:-0}" == "1" ]]; then
        args+=("--verbose")
    fi
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command xcrun notarytool "${args[@]}"
        log_info "[DRY-RUN] Skipping actual notarization."
        return 0
    fi
    
    # Submit and wait for result
    local tmpfile
    tmpfile=$(mktemp)
    
    log_info "Submitting to Apple notarytool..."
    log_info "This may take several minutes..."
    
    set +e
    xcrun notarytool "${args[@]}" 2>&1 | tee "$tmpfile"
    local submission_exit=${PIPESTATUS[0]}
    set -e
    
    local submission_output
    submission_output=$(cat "$tmpfile")
    rm -f "$tmpfile"
    
    # Parse submission UUID from output
    local submission_uuid
    submission_uuid=$(echo "$submission_output" | grep '^[[:space:]]*id:' | head -1 | awk '{print $NF}')
    
    log_debug "Submission UUID: $submission_uuid"
    
    # Check status
    if echo "$submission_output" | grep -q "status: Invalid"; then
        log_error "Notarization REJECTED"
        
        if [[ -n "$submission_uuid" ]]; then
            log_info ""
            log_info "Fetching rejection log for UUID: $submission_uuid"
            log_info "========================================"
            
            local reject_log
            reject_log=$(mktemp)
            xcrun notarytool log "$submission_uuid" --keychain-profile "$KEYCHAIN_PROFILE" 2>&1 | tee "$reject_log" || true
            log_info ""
            log_info "=== Rejection log contents:"
            cat "$reject_log"
            log_info "========================================"
            rm -f "$reject_log"
        fi
        
        show_troubleshooting "$submission_uuid"
        
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    if echo "$submission_output" | grep -q "status: Accepted"; then
        log_ok "Notarization ACCEPTED"
        return 0
    fi
    
    if [[ $submission_exit -ne 0 ]]; then
        log_error "Notarization failed with exit code $submission_exit"
        show_troubleshooting "$submission_uuid"
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    return 0
}

# Staple the notarization ticket
staple() {
    local dist_path="$1"
    log_info "Stapling notarization ticket to: $dist_path"
    
    if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
        log_command "xcrun stapler staple \"$dist_path\""
        return 0
    fi
    
    if [[ ! -e "$dist_path" ]]; then
        log_warn "Skipping staple: $dist_path not found"
        return 0
    fi
    
    xcrun stapler staple "$dist_path"
}

# Notarize a file
notarize_file() {
    local file_path="$1"
    local file_type="$2"
    
    log_info ""
    log_info "========================================"
    log_info "Notarizing $file_type: $file_path"
    log_info "========================================"
    log_info ""
    
    local to_submit="$file_path"
    local temp_zip=""
    
    # For .app bundles need to be zipped for notarization
    if [[ "$file_type" == "app" ]]; then
        # Zip the .app for notarization
        temp_zip="${file_path}.zip"
        log_info "Zipping .app for notarization..."
        
        if [[ "${AW_DRY_RUN:-0}" == "1" ]]; then
            log_command "ditto -c -k --keepParent \"$file_path\" \"$temp_zip\""
        else
            # Remove existing zip if present
            if [[ -f "$temp_zip" ]]; then
                rm -f "$temp_zip"
            fi
            ditto -c -k --keepParent "$file_path" "$temp_zip"
        fi
        
        to_submit="$temp_zip"
    fi
    
    # Submit for notarization
    if [[ "$NOTARIZATION_METHOD" == "notarytool" ]]; then
        if ! submit_notarytool "$to_submit"; then
            # Clean up temp zip
            if [[ -n "$temp_zip" ]] && [[ -f "$temp_zip" ]]; then
                log_info "Cleaning up temporary zip: $temp_zip"
                rm -f "$temp_zip"
            fi
            return $EXIT_NOTARIZATION_FAILED
        fi
    else
        log_error "altool method not fully implemented in this version."
        log_error "Please use Xcode 13+ with notarytool."
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    # Clean up temp zip
    if [[ -n "$temp_zip" ]] && [[ -f "$temp_zip" ]]; then
        log_info "Cleaning up temporary zip: $temp_zip"
        rm -f "$temp_zip"
    fi
    
    # Staple the original file (not the zip)
    log_info ""
    log_info "Stapling notarization ticket..."
    staple "$file_path"
    
    return 0
}

# =====================================
# Main
# =====================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
            show_help
            ;;
            --dry-run)
            AW_DRY_RUN=1
            shift
            ;;
            --verbose|-v)
            AW_VERBOSE=1
            shift
            ;;
            --sign)
            AW_SIGN=true
            shift
            ;;
            --notarize)
            AW_NOTARIZE=true
            shift
            ;;
            *)
            log_error "Unknown argument: $1"
            show_help
            ;;
        esac
    done
    
    # Check what to do
    local do_sign=false
    local do_notarize=false
    
    if [[ "${AW_SIGN:-false}" == "true" ]]; then
        do_sign=true
    fi
    if [[ "${AW_NOTARIZE:-false}" == "true" ]]; then
        do_notarize=true
    fi
    
    # If neither specified, do both
    if [[ "$do_sign" == "false" && "$do_notarize" == "false" ]]; then
        log_info "Neither AW_SIGN nor AW_NOTARIZE set."
        log_info "Defaulting to both (if credentials are available)."
        # Check if signing credentials are set
        if [[ -n "${AW_IDENTITY:-}" ]] || [[ -n "${APPLE_PERSONALID:-}" ]]; then
            do_sign=true
        fi
        # Check if notarization credentials are set
        if [[ -n "${APPLE_EMAIL:-}" ]] && [[ -n "${APPLE_PASSWORD:-}" ]] && [[ -n "${APPLE_TEAMID:-}" ]]; then
            do_notarize=true
        fi
    fi
    
    if [[ "$do_sign" == "false" && "$do_notarize" == "false" ]]; then
        log_error "No action. Set AW_SIGN=true or AW_NOTARIZE=true."
        log_info ""
        log_info "Example:"
        log_info "  AW_SIGN=true AW_NOTARIZE=true ./scripts/notarize.sh"
        show_help
    fi
    
    # Header
    log_info "================================================================="
    log_info "ActivityWatch macOS Signing & Notarization"
    log_info "================================================================="
    log_info ""
    log_info "Configuration:"
    log_info "  Sign:        $do_sign"
    log_info "  Notarize:   $do_notarize"
    log_info "  Dry run:     ${AW_DRY_RUN:-0}"
    log_info "  App path:    $APP_PATH"
    log_info "  DMG path:    $DMG_PATH"
    log_info ""
    
    # Validate
    if [[ "$do_sign" == "true" ]]; then
        if ! validate_signing_credentials; then
            exit $EXIT_MISSING_CREDENTIALS
        fi
    fi
    
    # Validate notarization credentials if needed
    if [[ "$do_notarize" == "true" ]]; then
        if ! validate_notarization_credentials; then
            exit $EXIT_MISSING_CREDENTIALS
        fi
        
        # Detect tools
        if ! detect_tools; then
            exit $EXIT_MISSING_TOOLS
        fi
        
        # Store credentials
        store_credentials
    fi
    
    # Signing
    if [[ "$do_sign" == "true" ]]; then
        log_info ""
        log_info "================================================================="
        log_info "Phase 1: Code Signing"
        log_info "================================================================="
        
        # Sign .app first
        if sign_app; then
            log_ok ".app signing successful"
        else
            log_error ".app signing failed"
            exit $EXIT_SIGNING_FAILED
        fi
        
        # Then sign DMG if it exists
        if [[ -f "$DMG_PATH" ]]; then
            if sign_dmg; then
                log_ok "DMG signing successful"
            else
                log_error "DMG signing failed"
                exit $EXIT_SIGNING_FAILED
            fi
        fi
    fi
    
    # Notarization
    if [[ "$do_notarize" == "true" ]]; then
        log_info ""
        log_info "================================================================="
        log_info "Phase 2: Notarization"
        log_info "================================================================="
        
        # Notarize .app first
        if [[ -d "$APP_PATH" ]]; then
            if ! notarize_file "$APP_PATH" "app"; then
                log_error ".app notarization failed"
                exit $EXIT_NOTARIZATION_FAILED
            fi
        fi
        
        # Then notarize DMG if it exists
        if [[ -f "$DMG_PATH" ]]; then
            if ! notarize_file "$DMG_PATH" "dmg"; then
                log_error "DMG notarization failed"
                exit $EXIT_NOTARIZATION_FAILED
            fi
        fi
    fi
    
    # Success
    log_info ""
    log_info "================================================================="
    log_info "All operations completed successfully!"
    log_info "================================================================="
    log_info ""
    log_ok "Summary:"
    log_ok "  Signing:      $do_sign"
    log_ok "  Notarization: $do_notarize"
    log_info ""
    
    show_troubleshooting ""
    
    exit $EXIT_SUCCESS
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
