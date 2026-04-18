#!/bin/bash
set -e

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=false
VERBOSE=false

APPLE_EMAIL=${APPLE_EMAIL:-}
APPLE_PASSWORD=${APPLE_PASSWORD:-}
APPLE_TEAMID=${APPLE_TEAMID:-}
APPLE_PERSONALID=${APPLE_PERSONALID:-}

KEYCHAIN_PROFILE="activitywatch-$APPLE_PERSONALID"
BUNDLE_ID="net.activitywatch.ActivityWatch"
APP_PATH="dist/ActivityWatch.app"
DMG_PATH="dist/ActivityWatch.dmg"

EXIT_SUCCESS=0
EXIT_ERROR=1
EXIT_MISSING_CREDENTIALS=2
EXIT_MISSING_TOOLS=3
EXIT_INVALID_ARGS=4
EXIT_NOTARIZATION_FAILED=5

echoerr() { echo "$@" 1>&2; }
log_info() { echo "[INFO] $@"; }
log_warn() { echo "[WARN] $@" 1>&2; }
log_error() { echo "[ERROR] $@" 1>&2; }

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Notarize and staple macOS bundles (.app, .dmg) using Apple's notary service.

Options:
    --dry-run       Only perform environment/tool checks, do not submit to Apple
    --verbose       Enable verbose output
    --help          Show this help message

Required Environment Variables:
    APPLE_EMAIL     Apple ID email address
    APPLE_PASSWORD  App-specific password (https://support.apple.com/en-us/HT204397)
    APPLE_TEAMID    Team ID (for individual developers, use your Developer ID)
    APPLE_PERSONALID Code signing identity (e.g., "Developer ID Application: Your Name")

Example:
    export APPLE_EMAIL="dev@example.com"
    export APPLE_PASSWORD="xxxx-xxxx-xxxx-xxxx"
    export APPLE_TEAMID="XXXXXXXXXX"
    export APPLE_PERSONALID="Developer ID Application: John Doe (XXXXXXXXXX)"
    ./$SCRIPT_NAME

    # Dry run mode
    ./$SCRIPT_NAME --dry-run
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_usage
                exit $EXIT_SUCCESS
                ;;
            *)
                log_error "Unknown argument: $1"
                show_usage
                exit $EXIT_INVALID_ARGS
                ;;
        esac
    done
}

check_credentials() {
    local missing=()
    
    if [[ -z "$APPLE_EMAIL" ]]; then
        missing+=("APPLE_EMAIL")
    fi
    if [[ -z "$APPLE_PASSWORD" ]]; then
        missing+=("APPLE_PASSWORD")
    fi
    if [[ -z "$APPLE_TEAMID" ]]; then
        missing+=("APPLE_TEAMID")
    fi
    if [[ -z "$APPLE_PERSONALID" ]]; then
        missing+=("APPLE_PERSONALID")
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing[@]}"; do
            echoerr "  - $var"
        done
        echoerr
        log_error "Example configuration:"
        cat << 'EOF' >&2

  export APPLE_EMAIL="your-apple-id@example.com"
  export APPLE_PASSWORD="xxxx-xxxx-xxxx-xxxx"   # App-specific password
  export APPLE_TEAMID="XXXXXXXXXX"               # Team ID from developer.apple.com
  export APPLE_PERSONALID="Developer ID Application: Your Name (XXXXXXXXXX)"

Notes:
  - APPLE_PASSWORD: Generate at https://appleid.apple.com/account/manage
  - APPLE_TEAMID: Found in Apple Developer account > Membership
  - APPLE_PERSONALID: Find using 'security find-identity -v -p codesigning'
EOF
        exit $EXIT_MISSING_CREDENTIALS
    fi
    
    log_info "All required credentials are present"
    if $VERBOSE; then
        log_info "  APPLE_EMAIL: $APPLE_EMAIL"
        log_info "  APPLE_TEAMID: $APPLE_TEAMID"
        log_info "  APPLE_PERSONALID: $APPLE_PERSONALID"
        log_info "  KEYCHAIN_PROFILE: $KEYCHAIN_PROFILE"
    fi
}

check_xcrun_tool() {
    local tool_name="$1"
    xcrun -f "$tool_name" >/dev/null 2>&1
}

NOTARIZATION_METHOD=""

detect_tools() {
    local has_notarytool=false
    local has_altool=false
    local has_stapler=false
    
    log_info "Detecting notarization tools..."
    
    if check_xcrun_tool notarytool; then
        has_notarytool=true
        log_info "  ✓ notarytool (Xcode >= 13) - PREFERRED"
    else
        log_info "  ✗ notarytool not found"
    fi
    
    if check_xcrun_tool altool; then
        has_altool=true
        log_info "  ✓ altool (Xcode < 13) - FALLBACK"
    else
        log_info "  ✗ altool not found"
    fi
    
    if check_xcrun_tool stapler; then
        has_stapler=true
        log_info "  ✓ stapler"
    else
        log_info "  ✗ stapler not found"
    fi
    
    if ! $has_stapler; then
        log_error "Required tool 'stapler' not found. Xcode command line tools required."
        exit $EXIT_MISSING_TOOLS
    fi
    
    if $has_notarytool; then
        NOTARIZATION_METHOD="run_notarytool"
    elif $has_altool; then
        NOTARIZATION_METHOD="run_altool"
    else
        log_error "No notarization tool found. Requires Xcode 13+ (notarytool) or Xcode < 13 (altool)."
        exit $EXIT_MISSING_TOOLS
    fi
}

run_notarytool() {
    local dist_path="$1"
    local dist_name
    dist_name="$(basename "$dist_path")"
    
    log_info "Notarizing $dist_name using notarytool..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would store credentials to keychain profile: $KEYCHAIN_PROFILE"
        log_info "[DRY-RUN] Would submit $dist_path to notary service and wait"
        log_info "[DRY-RUN] Notarization would complete for $dist_name"
        return $EXIT_SUCCESS
    fi
    
    log_info "Storing credentials to keychain profile: $KEYCHAIN_PROFILE"
    if ! xcrun notarytool store-credentials "$KEYCHAIN_PROFILE" \
        --apple-id "$APPLE_EMAIL" \
        --team-id "$APPLE_TEAMID" \
        --password "$APPLE_PASSWORD"; then
        log_error "Failed to store credentials in keychain"
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    log_info "Submitting $dist_path to notary service (this may take several minutes)..."
    local tmpfile
    tmpfile="$(mktemp)"
    if ! xcrun notarytool submit "$dist_path" \
        --keychain-profile "$KEYCHAIN_PROFILE" \
        --wait 2>&1 | tee "$tmpfile"; then
        local submission_exit=${PIPESTATUS[0]}
        local submission_output
        submission_output="$(cat "$tmpfile")"
        rm -f "$tmpfile"
        
        if echo "$submission_output" | grep -q "status: Invalid"; then
            local uuid
            uuid="$(echo "$submission_output" | grep '^[[:space:]]*id:' | head -1 | awk '{print $NF}')"
            if [[ -n "$uuid" ]]; then
                log_error "Notarization rejected (status: Invalid) - fetching rejection log for UUID: $uuid"
                echo "==================== REJECTION LOG ===================="
                xcrun notarytool log "$uuid" --keychain-profile "$KEYCHAIN_PROFILE" 2>&1 || true
                echo "==================== END OF LOG ===================="
            fi
        fi
        
        log_error "Notarization submission failed with exit code: $submission_exit"
        return $EXIT_NOTARIZATION_FAILED
    fi
    rm -f "$tmpfile"
    
    log_info "Notarization completed successfully for $dist_name"
    return $EXIT_SUCCESS
}

run_altool() {
    local dist_path="$1"
    local dist_name
    dist_name="$(basename "$dist_path")"
    
    log_info "Notarizing $dist_name using altool (Xcode < 13)..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would store password to keychain item: $KEYCHAIN_PROFILE"
        log_info "[DRY-RUN] Would submit $dist_path for notarization"
        log_info "[DRY-RUN] Would poll for status using UUID"
        log_info "[DRY-RUN] Notarization would complete for $dist_name"
        return $EXIT_SUCCESS
    fi
    
    log_info "Storing password to keychain item: $KEYCHAIN_PROFILE"
    if ! xcrun altool --store-password-in-keychain-item "$KEYCHAIN_PROFILE" \
        -u "$APPLE_EMAIL" -p "$APPLE_PASSWORD"; then
        log_error "Failed to store password in keychain"
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    log_info "Submitting $dist_path for notarization..."
    local upload_output
    upload_output="$(xcrun altool --notarize-app -t osx \
        -f "$dist_path" \
        --primary-bundle-id "$BUNDLE_ID" \
        -u "$APPLE_EMAIL" \
        --password "@keychain:$KEYCHAIN_PROFILE" \
        --output-format xml 2>&1)"
    
    if $VERBOSE; then
        log_info "Upload response:"
        echo "$upload_output"
    fi
    
    local uuid
    uuid="$(/usr/libexec/PlistBuddy -c "Print :notarization-upload:RequestUUID" /dev/stdin 2>/dev/null <<< "$upload_output" || echo "")"
    
    if [[ -z "$uuid" ]]; then
        log_error "Failed to extract RequestUUID from altool response"
        log_error "Response was:"
        echoerr "$upload_output"
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    log_info "Notarization request UUID: $uuid"
    
    local attempt=0
    local max_attempts=60
    local sleep_interval=30
    
    log_info "Polling for notarization status (timeout: $((max_attempts * sleep_interval)) seconds)..."
    
    while [[ $attempt -lt $max_attempts ]]; do
        attempt=$((attempt + 1))
        
        local status_output
        status_output="$(xcrun altool --notarization-info "$uuid" \
            -u "$APPLE_EMAIL" \
            -p "$APPLE_PASSWORD" \
            --output-format xml 2>&1)"
        
        if $VERBOSE; then
            log_info "Poll attempt $attempt/$max_attempts response:"
            echo "$status_output"
        fi
        
        local status
        status="$(/usr/libexec/PlistBuddy -c "Print :notarization-info:Status" /dev/stdin 2>/dev/null <<< "$status_output" || echo "")"
        
        if [[ -z "$status" ]]; then
            log_warn "Could not extract status from response, will retry..."
            sleep $sleep_interval
            continue
        fi
        
        log_info "Poll attempt $attempt/$max_attempts: status=$status"
        
        if [[ "$status" == "in progress" ]]; then
            sleep $sleep_interval
            continue
        elif [[ "$status" == "success" ]]; then
            log_info "Notarization completed successfully for $dist_name"
            return $EXIT_SUCCESS
        elif [[ "$status" == "invalid" ]]; then
            log_error "Notarization rejected for $dist_name"
            local log_url
            log_url="$(/usr/libexec/PlistBuddy -c "Print :notarization-info:LogFileURL" /dev/stdin 2>/dev/null <<< "$status_output" || echo "")"
            if [[ -n "$log_url" ]]; then
                log_error "Rejection log URL: $log_url"
                echo "==================== FETCHING REJECTION LOG ===================="
                curl -s "$log_url" 2>&1 || echo "Failed to fetch log from $log_url"
                echo "==================== END OF LOG ===================="
            fi
            return $EXIT_NOTARIZATION_FAILED
        else
            log_warn "Unknown status: $status, will retry..."
            sleep $sleep_interval
        fi
    done
    
    log_error "Notarization timed out after $((max_attempts * sleep_interval)) seconds"
    log_error "Last UUID: $uuid"
    return $EXIT_NOTARIZATION_FAILED
}

run_stapler() {
    local dist_path="$1"
    local dist_name
    dist_name="$(basename "$dist_path")"
    
    log_info "Stapling notarization ticket to $dist_name..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would staple ticket to $dist_path"
        log_info "[DRY-RUN] Stapling would complete for $dist_name"
        return $EXIT_SUCCESS
    fi
    
    if ! xcrun stapler staple "$dist_path"; then
        log_error "Failed to staple ticket to $dist_name"
        return $EXIT_ERROR
    fi
    
    log_info "Stapling completed successfully for $dist_name"
    return $EXIT_SUCCESS
}

notarize_and_staple() {
    local dist_path="$1"
    local notarization_method="$2"
    local is_app=false
    local zip_path=""
    
    if [[ -d "$dist_path" && "$dist_path" == *.app ]]; then
        is_app=true
        zip_path="${dist_path}.zip"
        
        log_info "Creating ZIP archive from .app bundle: $dist_path"
        if $DRY_RUN; then
            log_info "[DRY-RUN] Would run: ditto -c -k --keepParent \"$dist_path\" \"$zip_path\""
        else
            ditto -c -k --keepParent "$dist_path" "$zip_path"
        fi
        dist_path="$zip_path"
    fi
    
    if ! $notarization_method "$dist_path"; then
        if $is_app && [[ -n "$zip_path" ]]; then
            rm -f "$zip_path" 2>/dev/null || true
        fi
        return $EXIT_NOTARIZATION_FAILED
    fi
    
    if $is_app && [[ -n "$zip_path" ]] && ! $DRY_RUN; then
        rm -f "$zip_path"
        dist_path="${dist_path%.zip}"
    fi
    
    if ! run_stapler "$dist_path"; then
        return $EXIT_ERROR
    fi
    
    return $EXIT_SUCCESS
}

main() {
    parse_args "$@"
    
    log_info "========================================"
    log_info "ActivityWatch Notarization Script"
    log_info "========================================"
    if $DRY_RUN; then
        log_info "Mode: DRY-RUN (no actual submissions)"
    fi
    echo
    
    check_credentials
    
    detect_tools
    log_info "Selected notarization method: $NOTARIZATION_METHOD"
    echo
    
    local has_app=false
    local has_dmg=false
    
    if [[ -d "$APP_PATH" ]]; then
        has_app=true
        log_info "Found app bundle: $APP_PATH"
    else
        log_info "App bundle not found: $APP_PATH (skipping)"
    fi
    
    if [[ -f "$DMG_PATH" ]]; then
        has_dmg=true
        log_info "Found disk image: $DMG_PATH"
    else
        log_info "Disk image not found: $DMG_PATH (skipping)"
    fi
    
    if ! $has_app && ! $has_dmg; then
        log_error "Neither app bundle nor disk image found for notarization"
        log_error "Expected: $APP_PATH or $DMG_PATH"
        exit $EXIT_ERROR
    fi
    
    echo
    log_info "========================================"
    log_info "Starting notarization process"
    log_info "========================================"
    echo
    
    local overall_status=$EXIT_SUCCESS
    
    if $has_app; then
        echo
        log_info "=== Processing: $APP_PATH ==="
        if notarize_and_staple "$APP_PATH" "$NOTARIZATION_METHOD"; then
            log_info "✓ App bundle notarized and stapled successfully"
        else
            log_error "✗ App bundle notarization failed"
            overall_status=$EXIT_NOTARIZATION_FAILED
        fi
    fi
    
    if $has_dmg; then
        echo
        log_info "=== Processing: $DMG_PATH ==="
        if notarize_and_staple "$DMG_PATH" "$NOTARIZATION_METHOD"; then
            log_info "✓ Disk image notarized and stapled successfully"
        else
            log_error "✗ Disk image notarization failed"
            overall_status=$EXIT_NOTARIZATION_FAILED
        fi
    fi
    
    echo
    log_info "========================================"
    if [[ $overall_status -eq $EXIT_SUCCESS ]]; then
        log_info "NOTARIZATION COMPLETED SUCCESSFULLY"
        if $DRY_RUN; then
            log_info "(Dry run - no actual submissions were made)"
        fi
    else
        log_error "NOTARIZATION FAILED"
    fi
    log_info "========================================"
    
    exit $overall_status
}

main "$@"
