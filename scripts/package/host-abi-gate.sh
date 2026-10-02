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
# Usage: host-abi-gate.sh <bundle-dir|bundle.zip|bundle.AppImage> [...]
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
    echo "Usage: $0 <bundle-dir|bundle.zip|bundle.AppImage> [...]" >&2
    exit 2
fi

WORKDIR=$(mktemp -d)
FOUND_LOG="$WORKDIR/found.txt"
touch "$FOUND_LOG"
trap 'rm -rf "$WORKDIR"' EXIT

# Prints (and records) any path under $1 whose basename matches a host-ABI
# library. Symlinks are included: a forbidden .so name present only as a link
# to a differently named file is still bundled, and the loader resolves it by
# that name. A failing `find` aborts the gate — an incomplete scan must not be
# able to report PASS.
scan_dir() {
    local dir="$1"
    local listing
    if ! listing=$(find "$dir" \( -type f -o -type l \) \
        \( -name '*.so' -o -name '*.so.*' \) -print); then
        echo "ERROR: find failed while scanning $dir — gate cannot verify the bundle" >&2
        exit 2
    fi
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        local base target_base
        base=$(basename "$path")
        # Resolve symlink target so a differently-named link (e.g. libfoo.so ->
        # libwayland-client.so.0) is caught by its target's name too.
        target_base=""
        if [ -L "$path" ]; then
            local resolved
            resolved=$(readlink -f "$path" 2>/dev/null || true)
            [ -n "$resolved" ] && target_base=$(basename "$resolved")
        fi
        local matched=0
        for lib in "${HOST_ABI_LIBS[@]}"; do
            if [ "$base" = "$lib" ] || [[ "$base" == "$lib".so* ]]; then
                matched=1; break
            fi
            if [ -n "$target_base" ] && { [ "$target_base" = "$lib" ] || [[ "$target_base" == "$lib".so* ]]; }; then
                matched=1; break
            fi
        done
        if [ "$matched" -eq 1 ]; then
            printf '%s\n' "$path"
            printf '%s\n' "$path" >> "$FOUND_LOG"
        fi
    done <<< "$listing"
}

# Extracts an AppImage into $2. Mirrors scripts/package/abi-gate.sh: prefer
# unsquashfs (explicit SquashFS offset), else the AppImage self-extract with
# FUSE disabled. Returns non-zero when neither works, so the caller can abort
# rather than silently skip the scan.
extract_appimage() {
    local ai dest
    # Resolve to an absolute path so the self-extract below works from any cwd,
    # whether the caller passed a relative or an absolute path.
    ai=$(realpath "$1")
    dest="$2"
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
    pushd "$WORKDIR" >/dev/null
    APPIMAGE_EXTRACT_AND_RUN=1 "$ai" --appimage-extract &>/dev/null || true
    popd >/dev/null
    if [ -d "$WORKDIR/squashfs-root" ]; then
        mv "$WORKDIR/squashfs-root" "$dest"
        echo "  Extracted AppImage via --appimage-extract"
        return 0
    fi
    return 1
}

scan_path() {
    local arg="$1"
    case "$arg" in
        *.zip)
            local dest="$WORKDIR/zip"
            mkdir -p "$dest"
            unzip -q "$arg" -d "$dest"
            echo "=== Scanning zip: $arg ==="
            scan_dir "$dest"
            ;;
        *.AppImage)
            local dest="$WORKDIR/appimage"
            mkdir -p "$dest"
            if extract_appimage "$arg" "$dest"; then
                echo "=== Scanning AppImage: $arg ==="
                scan_dir "$dest"
            else
                echo "ERROR: could not extract $(basename "$arg") — host-ABI scan is required; aborting" >&2
                exit 2
            fi
            ;;
        *)
            if [ -d "$arg" ]; then
                echo "=== Scanning dir: $arg ==="
                scan_dir "$arg"
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
