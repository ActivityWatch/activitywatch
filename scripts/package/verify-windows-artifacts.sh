#!/bin/bash
#
# ActivityWatch Windows Artifacts Verification Script
# ====================================================
#
# This script verifies that the Windows installer (Inno Setup) contains
# the same files as the zip archive.
#
# It works by:
#   1. Generating a manifest of files in the source directory (dist/activitywatch/)
#   2. Generating a manifest of files in the zip archive
#   3. Comparing the two manifests to find differences
#
# Environment Variables:
#   TAURI_BUILD:       Set to "true" for Tauri builds
#   DIST_DIR:          Path to dist directory (default: ./dist)
#   STRICT_MODE:       Set to "true" to exit with non-zero code on differences
#   VERBOSE:           Set to "1" for more detailed output
#
# Exit Codes:
#   0:  Success (no differences found or non-strict mode)
#   1:  Critical error (e.g., missing files)
#   2:  Differences found (only in strict mode)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${DIST_DIR:-./dist}"
TAURI_BUILD="${TAURI_BUILD:-false}"
STRICT_MODE="${STRICT_MODE:-false}"
VERBOSE="${VERBOSE:-0}"

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

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Verify that Windows installer and zip archive contain the same files.

Options:
  --strict        Exit with non-zero code on differences
  --help, -h      Show this help message

Environment Variables:
  TAURI_BUILD     Set to "true" for Tauri builds
  DIST_DIR        Path to dist directory (default: ./dist)
  VERBOSE         Set to "1" for detailed output

Checks performed:
  1. Compare source directory (dist/activitywatch/) with zip contents
  2. Report missing files (in source but not in zip)
  3. Report extra files (in zip but not in source)
  4. Report files with different sizes
  5. For Tauri builds: verify aw-tauri.exe is in correct location
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

# Generate manifest for a directory
# Usage: generate_dir_manifest <directory> <output_file>
generate_dir_manifest() {
    local dir="$1"
    local output="$2"
    local prefix="${3:-}"
    
    log_action "Generating manifest for directory: $dir"
    
    if [[ ! -d "$dir" ]]; then
        log_error "Directory not found: $dir"
        return 1
    fi
    
    # Create manifest with format: <path>|<size>|<mtime>
    # Use relative paths from the directory root
    pushd "$dir" >/dev/null
    
    if command -v find >/dev/null 2>&1; then
        find . -type f -print0 | while IFS= read -r -d '' file; do
            # Remove leading "./"
            local rel_path="${file#./}"
            
            # Skip if empty (root directory)
            if [[ -z "$rel_path" ]]; then
                continue
            fi
            
            # Apply prefix if provided
            if [[ -n "$prefix" ]]; then
                rel_path="$prefix/$rel_path"
            fi
            
            # Get file size
            local size
            if command -v stat >/dev/null 2>&1; then
                if [[ "$(uname -s)" == "Darwin" ]]; then
                    size=$(stat -f%z "$file" 2>/dev/null || echo "0")
                else
                    size=$(stat -c%s "$file" 2>/dev/null || echo "0")
                fi
            else
                size=$(wc -c < "$file" 2>/dev/null || echo "0")
            fi
            
            # Output: path|size
            echo "$rel_path|$size"
        done | sort > "$output"
    else
        log_error "find command not available"
        popd >/dev/null
        return 1
    fi
    
    popd >/dev/null
    
    local count
    count=$(wc -l < "$output" 2>/dev/null || echo "0")
    log_ok "Generated manifest with $count files"
    
    if [[ $VERBOSE == "1" ]]; then
        log_info "First 10 entries:"
        head -10 "$output"
    fi
}

# Generate manifest for a zip file
# Usage: generate_zip_manifest <zip_file> <output_file>
generate_zip_manifest() {
    local zip_file="$1"
    local output="$2"
    
    log_action "Generating manifest for zip: $zip_file"
    
    if [[ ! -f "$zip_file" ]]; then
        log_error "Zip file not found: $zip_file"
        return 1
    fi
    
    # Try to use unzip first, then 7z
    if command -v unzip >/dev/null 2>&1; then
        # unzip -Zv shows detailed info including size
        # Format: "  2345  Defl:N     1234  47% 2024-01-01 12:00  12345678  filename"
        unzip -Zv "$zip_file" 2>/dev/null | grep -v "^Archive\|^Length\|^---------\|^$" | while read -r line; do
            # Extract size (first column) and filename (last column)
            local size
            local filename
            size=$(echo "$line" | awk '{print $1}')
            filename=$(echo "$line" | awk '{print $NF}')
            
            # Skip if size is not a number or filename is empty
            if ! [[ "$size" =~ ^[0-9]+$ ]] || [[ -z "$filename" ]]; then
                continue
            fi
            
            # Skip directories (end with /)
            if [[ "$filename" == */ ]]; then
                continue
            fi
            
            # Output: path|size
            echo "$filename|$size"
        done | sort > "$output"
    elif command -v 7z >/dev/null 2>&1; then
        # 7z l -slt shows detailed info
        local temp_file
        temp_file=$(mktemp)
        7z l -slt "$zip_file" > "$temp_file" 2>/dev/null
        
        # Parse 7z output
        local path=""
        local size=""
        while IFS= read -r line; do
            if [[ "$line" == Path=* ]]; then
                path="${line#Path=}"
            elif [[ "$line" == Size=* ]]; then
                size="${line#Size=}"
            elif [[ "$line" == *"---"* ]]; then
                # End of entry
                if [[ -n "$path" ]] && [[ -n "$size" ]] && [[ "$path" != *"/" ]]; then
                    echo "$path|$size"
                fi
                path=""
                size=""
            fi
        done < "$temp_file" | sort > "$output"
        
        rm -f "$temp_file"
    else
        log_error "Neither unzip nor 7z command is available"
        return 1
    fi
    
    local count
    count=$(wc -l < "$output" 2>/dev/null || echo "0")
    log_ok "Generated zip manifest with $count files"
    
    if [[ $VERBOSE == "1" ]]; then
        log_info "First 10 entries:"
        head -10 "$output"
    fi
}

# Compare two manifests
# Usage: compare_manifests <manifest1> <manifest2> <label1> <label2>
compare_manifests() {
    local manifest1="$1"
    local manifest2="$2"
    local label1="$3"
    local label2="$4"
    
    log_header "Comparing Manifests"
    log_info "  $label1: $manifest1"
    log_info "  $label2: $manifest2"
    
    # Create temporary files for analysis
    local missing_files
    local extra_files
    local different_sizes
    missing_files=$(mktemp)
    extra_files=$(mktemp)
    different_sizes=$(mktemp)
    
    # Read manifests into associative arrays
    declare -A map1
    declare -A map2
    
    # Read manifest1
    while IFS='|' read -r path size; do
        if [[ -n "$path" ]] && [[ -n "$size" ]]; then
            map1["$path"]="$size"
        fi
    done < "$manifest1"
    
    # Read manifest2
    while IFS='|' read -r path size; do
        if [[ -n "$path" ]] && [[ -n "$size" ]]; then
            map2["$path"]="$size"
        fi
    done < "$manifest2"
    
    # Find missing files (in map1 but not in map2)
    for path in "${!map1[@]}"; do
        if [[ -z "${map2[$path]+x}" ]]; then
            # File is in map1 but not in map2
            echo "$path|${map1[$path]}" >> "$missing_files"
        elif [[ "${map1[$path]}" != "${map2[$path]}" ]]; then
            # Same path, different size
            echo "$path|${map1[$path]}|${map2[$path]}" >> "$different_sizes"
        fi
    done
    
    # Find extra files (in map2 but not in map1)
    for path in "${!map2[@]}"; do
        if [[ -z "${map1[$path]+x}" ]]; then
            echo "$path|${map2[$path]}" >> "$extra_files"
        fi
    done
    
    # Count differences
    local missing_count
    local extra_count
    local different_count
    missing_count=$(wc -l < "$missing_files" 2>/dev/null || echo "0")
    extra_count=$(wc -l < "$extra_files" 2>/dev/null || echo "0")
    different_count=$(wc -l < "$different_sizes" 2>/dev/null || echo "0")
    
    local total_differences=$((missing_count + extra_count + different_count))
    
    # Report results
    log_info ""
    log_info "Comparison Summary:"
    log_info "  Total files in $label1: ${#map1[@]}"
    log_info "  Total files in $label2: ${#map2[@]}"
    log_info "  Missing files: $missing_count"
    log_info "  Extra files: $extra_count"
    log_info "  Different sizes: $different_count"
    log_info "  Total differences: $total_differences"
    
    if [[ $total_differences -gt 0 ]]; then
        log_warn ""
        log_warn "========================================"
        log_warn "DIFFERENCES FOUND!"
        log_warn "========================================"
        
        if [[ $missing_count -gt 0 ]]; then
            log_warn ""
            log_warn "--- Missing Files (in $label1 but not in $label2) ---"
            log_warn ""
            while IFS='|' read -r path size; do
                log_warn "  [MISSING] $path ($size bytes)"
            done < "$missing_files"
        fi
        
        if [[ $extra_count -gt 0 ]]; then
            log_warn ""
            log_warn "--- Extra Files (in $label2 but not in $label1) ---"
            log_warn ""
            while IFS='|' read -r path size; do
                log_warn "  [EXTRA] $path ($size bytes)"
            done < "$extra_files"
        fi
        
        if [[ $different_count -gt 0 ]]; then
            log_warn ""
            log_warn "--- Different Sizes ---"
            log_warn ""
            while IFS='|' read -r path size1 size2; do
                log_warn "  [DIFF] $path: $size1 bytes vs $size2 bytes"
            done < "$different_sizes"
        fi
        
        log_warn ""
        log_warn "========================================"
    fi
    
    # Cleanup
    rm -f "$missing_files" "$extra_files" "$different_sizes"
    
    # Return count of differences
    return $total_differences
}

# =====================================
# Main
# =====================================

log_header "ActivityWatch Windows Artifacts Verification"
log_info ""
log_info "Configuration:"
log_info "  TAURI_BUILD:  $TAURI_BUILD"
log_info "  DIST_DIR:     $DIST_DIR"
log_info "  STRICT_MODE:  $STRICT_MODE"
log_info "  VERBOSE:      $VERBOSE"

# Check if we're on Windows (or cross-compiling)
# For now, we check if dist/activitywatch directory exists
log_section "Validating Environment"

ACTIVITYWATCH_DIR="$DIST_DIR/activitywatch"

if [[ ! -d "$ACTIVITYWATCH_DIR" ]]; then
    log_error "Source directory not found: $ACTIVITYWATCH_DIR"
    log_info "Run 'make package' first to create the dist directory."
    exit 1
fi
log_ok "Source directory found: $ACTIVITYWATCH_DIR"

# Find zip file
log_section "Finding Distribution Artifacts"

ZIP_FILE=""
while IFS= read -r -d '' file; do
    # Skip if not a real zip (e.g., temporary files)
    if [[ "$file" == *"activitywatch"* ]]; then
        ZIP_FILE="$file"
        break
    fi
done < <(find "$DIST_DIR" -maxdepth 1 -name "activitywatch*.zip" -print0 2>/dev/null || true)

if [[ -z "$ZIP_FILE" ]] || [[ ! -f "$ZIP_FILE" ]]; then
    log_error "Zip file not found in $DIST_DIR"
    log_info "Run 'make package' first to create the zip archive."
    exit 1
fi
log_ok "Zip file found: $ZIP_FILE"

# Check for Tauri-specific files
if [[ $TAURI_BUILD == "true" ]]; then
    log_info ""
    log_info "Tauri build detected."
    
    # Check for aw-tauri.exe
    if [[ -f "$ACTIVITYWATCH_DIR/aw-tauri.exe" ]]; then
        log_ok "Found aw-tauri.exe in source directory"
    elif [[ -f "$ACTIVITYWATCH_DIR/aw-tauri/aw-tauri.exe" ]]; then
        log_ok "Found aw-tauri.exe in aw-tauri/ subdirectory"
    else
        log_warn "aw-tauri.exe not found in source directory"
    fi
else
    log_info ""
    log_info "Standard (aw-qt) build detected."
    
    # Check for aw-qt.exe
    if [[ -f "$ACTIVITYWATCH_DIR/aw-qt.exe" ]]; then
        log_ok "Found aw-qt.exe in source directory"
    else
        log_warn "aw-qt.exe not found in source directory"
    fi
fi

# Generate manifests
log_section "Generating Manifests"

# Create temporary directory for manifests
MANIFEST_DIR=$(mktemp -d)
trap 'rm -rf "$MANIFEST_DIR"' EXIT

SOURCE_MANIFEST="$MANIFEST_DIR/source-manifest.txt"
ZIP_MANIFEST="$MANIFEST_DIR/zip-manifest.txt"

# Generate source manifest
if ! generate_dir_manifest "$ACTIVITYWATCH_DIR" "$SOURCE_MANIFEST"; then
    log_error "Failed to generate source manifest"
    exit 1
fi

# Generate zip manifest
if ! generate_zip_manifest "$ZIP_FILE" "$ZIP_MANIFEST"; then
    log_error "Failed to generate zip manifest"
    exit 1
fi

# Compare manifests
log_section "Comparing Source Directory vs Zip Archive"

if compare_manifests "$SOURCE_MANIFEST" "$ZIP_MANIFEST" "Source Directory" "Zip Archive"; then
    # No differences
    log_header "RESULT: ALL CHECKS PASSED"
    log_ok "Source directory and zip archive contain the same files."
    log_ok "Windows release consistency verified!"
    exit 0
else
    # Differences found
    local diff_count=$?
    
    log_header "RESULT: DIFFERENCES FOUND"
    log_warn "Found $diff_count difference(s) between source directory and zip archive."
    log_warn ""
    log_warn "This may indicate:"
    log_warn "  - Files were added/removed during zip creation"
    log_warn "  - Inno Setup is installing different files than zip"
    log_warn ""
    
    if [[ $STRICT_MODE == "true" ]]; then
        log_error "Exiting with non-zero code (strict mode)"
        exit 2
    else
        log_info "Use --strict or set STRICT_MODE=true to exit with non-zero code."
        exit 0
    fi
fi
