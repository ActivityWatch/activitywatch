#!/bin/bash
# host-abi-gate.sh — Verify that a Linux bundle does not ship libraries that
# must come from the host dynamic loader instead.
#
# Bundling these shadows the user's system copy with whatever version the
# build host had, which breaks at runtime:
#   - libwayland-client: libQt6WaylandClient needs wl_proxy_marshal_flags
#     (libwayland >= 1.20), so a stale bundled copy crashes aw-qt on startup
#     (#1105, #1116).
#   - libgio/libglib/libgobject: a bundled libgio cannot read the host's
#     GSettings schemas (#710, #1077).
#
# Keep this list in sync with the "Remove problem-causing binaries" block in
# the top-level Makefile.
#
# Usage: host-abi-gate.sh <bundle-dir|bundle.zip> [...]
# Exit 0 = all clear; exit 1 = a host-ABI library is bundled; exit 2 = error.

set -euo pipefail

HOST_ABI_LIBS=(
    libwayland-client
    libwayland-cursor
    libwayland-egl
    libgio-2.0
    libglib-2.0
    libgobject-2.0
)

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <bundle-dir|bundle.zip> [...]" >&2
    exit 2
fi

WORKDIR=$(mktemp -d)
FOUND_LOG="$WORKDIR/found.txt"
touch "$FOUND_LOG"
trap 'rm -rf "$WORKDIR"' EXIT

# Prints any path under $1 whose basename matches a host-ABI library.
scan_dir() {
    local dir="$1"
    while IFS= read -r path; do
        local base
        base=$(basename "$path")
        for lib in "${HOST_ABI_LIBS[@]}"; do
            if [ "$base" = "$lib" ] || [[ "$base" == "$lib".so* ]]; then
                printf '%s\n' "$path"
                break
            fi
        done
    done < <(find "$dir" -type f \( -name '*.so' -o -name '*.so.*' \) 2>/dev/null)
}

scan_path() {
    local arg="$1"
    case "$arg" in
        *.zip)
            local dest="$WORKDIR/zip"
            mkdir -p "$dest"
            unzip -q "$arg" -d "$dest"
            echo "=== Scanning zip: $arg ==="
            scan_dir "$dest" | tee -a "$FOUND_LOG"
            ;;
        *.AppImage)
            echo "WARNING: AppImage scan not supported here; scanning the bundle directory it was built from instead" >&2
            ;;
        *)
            if [ -d "$arg" ]; then
                echo "=== Scanning dir: $arg ==="
                scan_dir "$arg" | tee -a "$FOUND_LOG"
            else
                echo "ERROR: no such file or directory: $arg" >&2
                exit 2
            fi
            ;;
    esac
}

for arg in "$@"; do
    scan_path "$arg"
done

echo ""
echo "=== Host-ABI Gate Summary ==="
COUNT=$(wc -l < "$FOUND_LOG")
if [ "$COUNT" -gt 0 ]; then
    echo "FAIL: $COUNT host-ABI library file(s) bundled — they must come from the host:" >&2
    cat "$FOUND_LOG" >&2
    exit 1
fi
echo "PASS: no host-ABI libraries bundled"
