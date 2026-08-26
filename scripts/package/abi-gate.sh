#!/bin/bash
# abi-gate.sh — Verify that no bundled ELF requires a GLIBC symbol above
# GLIBC_2.28.  Run this after packaging to gate on the ABI floor.
#
# Usage: abi-gate.sh <file.zip> [<file.AppImage>]
# Exit 0 = all clear; exit 1 = ABI violation found; exit 2 = script error.
#
# For AppImage files, extraction requires either:
#   - `unsquashfs` (squashfs-tools package), or
#   - APPIMAGE_EXTRACT_AND_RUN=1 so the AppImage self-extracts without FUSE.
# If neither works the AppImage scan is skipped with a warning (not a failure).

set -euo pipefail

GLIBC_FLOOR_MAJOR=2
GLIBC_FLOOR_MINOR=28

WORKDIR=$(mktemp -d)
VIOLATION_LOG="$WORKDIR/violations.txt"
touch "$VIOLATION_LOG"
trap 'rm -rf "$WORKDIR"' EXIT

# Returns 0 (true) when the version string X.Y exceeds the floor.
glibc_exceeds_floor() {
    local ver="$1"
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -gt "$GLIBC_FLOOR_MAJOR" ]; then return 0; fi
    if [ "$major" -eq "$GLIBC_FLOOR_MAJOR" ] && \
       [ "$minor" -gt "$GLIBC_FLOOR_MINOR" ]; then return 0; fi
    return 1
}

scan_elfs() {
    local dir="$1" label="$2"
    echo "=== Scanning ELFs in: $label ==="
    local total=0 scanned=0
    while IFS= read -r elf; do
        total=$((total + 1))
        local versions
        versions=$(readelf --version-info "$elf" 2>/dev/null \
            | grep -oP 'GLIBC_[0-9]+\.[0-9]+(\.[0-9]+)?' \
            | sort -Vu) || true
        [ -z "$versions" ] && continue
        scanned=$((scanned + 1))
        while IFS= read -r sym; do
            local ver="${sym#GLIBC_}"
            if glibc_exceeds_floor "$ver"; then
                printf '  VIOLATION in %s: %s\n' "$(basename "$elf")" "$sym" \
                    | tee -a "$VIOLATION_LOG"
            fi
        done <<< "$versions"
    done < <(find "$dir" -type f -exec file {} + 2>/dev/null \
        | grep -E ': ELF ' | cut -d: -f1)
    echo "  ELFs with GLIBC refs: $scanned / $total files scanned"
}

extract_appimage() {
    local ai="$1" dest="$2"
    # Try unsquashfs first (reliable offset detection via SquashFS magic).
    if command -v unsquashfs &>/dev/null; then
        local offset
        offset=$(python3 -c "
import sys
data = open(sys.argv[1], 'rb').read()
for magic in (b'sqsh', b'hsqs'):
    idx = data.find(magic)
    if idx >= 0:
        print(idx)
        break
" "$ai" 2>/dev/null || true)
        if [ -n "$offset" ]; then
            if unsquashfs -dest "$dest" -offset "$offset" "$ai" &>/dev/null; then
                echo "  Extracted AppImage via unsquashfs (offset $offset)"
                return 0
            fi
        fi
    fi
    # Fallback: AppImage self-extract (needs APPIMAGE_EXTRACT_AND_RUN=1 in env).
    pushd "$WORKDIR" >/dev/null
    APPIMAGE_EXTRACT_AND_RUN=1 "$OLDPWD/$ai" --appimage-extract &>/dev/null || true
    popd >/dev/null
    if [ -d "$WORKDIR/squashfs-root" ]; then
        mv "$WORKDIR/squashfs-root" "$dest"
        echo "  Extracted AppImage via --appimage-extract"
        return 0
    fi
    return 1
}

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <file.zip> [<file.AppImage>]" >&2
    exit 2
fi

for arg in "$@"; do
    case "$arg" in
        *.zip)
            ZIPDIR="$WORKDIR/zip"
            mkdir -p "$ZIPDIR"
            unzip -q "$arg" -d "$ZIPDIR"
            scan_elfs "$ZIPDIR" "$(basename "$arg")"
            ;;
        *.AppImage)
            AI_DIR="$WORKDIR/appimage"
            mkdir -p "$AI_DIR"
            if extract_appimage "$arg" "$AI_DIR"; then
                scan_elfs "$AI_DIR" "$(basename "$arg")"
            else
                echo "ERROR: could not extract $(basename "$arg") — AppImage ABI scan is required; aborting" >&2
                exit 2
            fi
            ;;
        *)
            echo "WARNING: unrecognised file type: $arg — skipping" >&2
            ;;
    esac
done

echo ""
echo "=== ABI Gate Summary ==="
echo "GLIBC floor: GLIBC_${GLIBC_FLOOR_MAJOR}.${GLIBC_FLOOR_MINOR}"
VIOLATION_COUNT=$(wc -l < "$VIOLATION_LOG")
echo "Violations: $VIOLATION_COUNT"

if [ "$VIOLATION_COUNT" -gt 0 ]; then
    echo ""
    echo "Offending symbols:"
    cat "$VIOLATION_LOG"
    echo ""
    echo "FAIL: bundled ELFs exceed the glibc ${GLIBC_FLOOR_MAJOR}.${GLIBC_FLOOR_MINOR} ABI floor"
    exit 1
fi
echo "PASS: no GLIBC symbol above GLIBC_${GLIBC_FLOOR_MAJOR}.${GLIBC_FLOOR_MINOR} found"
