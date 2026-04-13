#!/bin/bash
set -e

# Build a macOS .app bundle for the Tauri-based ActivityWatch.
# This replaces the PyInstaller-based bundling used by aw-qt.

APP_NAME="ActivityWatch"
BUNDLE_ID="net.activitywatch.ActivityWatch"
VERSION="0.1.0"
ICON_PATH="aw-tauri/src-tauri/icons/icon.icns"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is designed to run on macOS only."
    exit 1
fi

if [ ! -d "dist/activitywatch" ]; then
    echo "Error: dist/activitywatch directory not found. Please build the project first."
    exit 1
fi

if [ ! -f "dist/activitywatch/aw-tauri" ]; then
    echo "Error: aw-tauri binary not found in dist/activitywatch/"
    exit 1
fi

echo "Cleaning previous builds..."
rm -rf "dist/${APP_NAME}.app"
mkdir -p "dist"

echo "Creating app bundle structure..."
mkdir -p "dist/${APP_NAME}.app/Contents/"{MacOS,Resources}

echo "Copying aw-tauri as main executable..."
cp "dist/activitywatch/aw-tauri" "dist/${APP_NAME}.app/Contents/MacOS/aw-tauri"
chmod +x "dist/${APP_NAME}.app/Contents/MacOS/aw-tauri"

echo "Copying components to Resources..."
for component in dist/activitywatch/*/; do
    if [ -d "$component" ]; then
        component_name=$(basename "$component")
        echo "  Copying $component_name..."
        mkdir -p "dist/${APP_NAME}.app/Contents/Resources/$component_name"
        cp -r "$component"/* "dist/${APP_NAME}.app/Contents/Resources/$component_name/"
    fi
done

echo "Fixing Python.framework symlink structure..."
# PyInstaller copies Python.framework using regular files/directories instead of
# preserving the standard macOS symlink layout. Without symlinks, codesign rejects
# the framework with "bundle format is ambiguous (could be app or framework)".
# Restore the canonical layout so codesign can sign it as a proper framework bundle:
#   Versions/Current -> <version>  (symlink)
#   Python -> Versions/Current/Python  (symlink)
#   Resources -> Versions/Current/Resources  (symlink)
#   Headers -> Versions/Current/Headers  (symlink, if present)
while IFS= read -r fw; do
    echo "  Fixing: $fw"
    # Find the actual version directory (e.g., "3.9"), skipping "Current"
    version_dir=$(ls "$fw/Versions/" 2>/dev/null | grep -v Current | head -1)
    if [ -z "$version_dir" ]; then
        echo "  Warning: No version directory found in $fw/Versions/, skipping"
        continue
    fi

    # Replace Versions/Current directory with a symlink to the version dir
    if [ -d "$fw/Versions/Current" ] && [ ! -L "$fw/Versions/Current" ]; then
        rm -rf "$fw/Versions/Current"
        ln -s "$version_dir" "$fw/Versions/Current"
    fi

    # Replace root-level copies with symlinks into Versions/Current/
    for item in Python Resources Headers; do
        if [ -e "$fw/$item" ] && [ ! -L "$fw/$item" ]; then
            rm -rf "$fw/$item"
            ln -s "Versions/Current/$item" "$fw/$item"
        fi
    done
done < <(find "dist/${APP_NAME}.app" -type d -name "*.framework" \
    | grep -i python)

echo "Setting executable permissions..."
find "dist/${APP_NAME}.app/Contents/Resources" -type f -name "aw-*" -exec chmod +x {} \;

echo "Copying app icon..."
if [ -f "$ICON_PATH" ]; then
    cp "$ICON_PATH" "dist/${APP_NAME}.app/Contents/Resources/icon.icns"
else
    echo "Warning: Icon file not found at $ICON_PATH"
fi

echo "Creating Info.plist..."
cat > "dist/${APP_NAME}.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleExecutable</key>
    <string>aw-tauri</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>ActivityWatch needs access to monitor application usage</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
</dict>
</plist>
EOF

echo "Creating PkgInfo..."
echo "APPL????" > "dist/${APP_NAME}.app/Contents/PkgInfo"

if [ -n "$APPLE_PERSONALID" ]; then
    echo "Signing app with identity: $APPLE_PERSONALID (inside-out, per-binary)"
    # codesign --deep is unreliable for bundles with PyInstaller helpers:
    # it doesn't reach all nested dylibs/so files and mishandles Python.framework
    # symlinks, leaving hundreds of binaries unsigned or invalidly signed.
    # The correct approach is inside-out: sign all Mach-O leaves first,
    # then .framework bundles, then the top-level .app last.
    # --timestamp is required for notarization (Apple rejects submissions without it).
    ENTITLEMENTS="scripts/package/entitlements.plist"

    sign_binary() {
        echo "  Signing: $1"
        codesign --force --options runtime --timestamp \
            --entitlements "$ENTITLEMENTS" \
            --sign "$APPLE_PERSONALID" \
            "$1"
    }

    # Step 1: Sign all Mach-O binary files (dylibs, .so files, standalone executables).
    # Use `xargs file` to batch all type queries in O(1) subprocess calls instead of
    # one `file` invocation per binary (PyInstaller bundles can contain hundreds of files).
    # Sort by path length descending so deeper binaries are signed before shallower containers.
    # IMPORTANT: Skip the main binary of .framework bundles (e.g. Python.framework/Python).
    # codesign treats those as ambiguous ("could be app or framework") when signed as
    # standalone files. They are correctly signed in Step 2 as part of the framework bundle.
    echo "  Signing Mach-O binary files..."
    while IFS= read -r f; do
        # Skip main binaries of bundle directories (.framework, .bundle, .plugin) —
        # they'll be signed as part of the bundle in Step 2. Signing them standalone
        # causes "bundle format is ambiguous" errors from codesign.
        parent_dir="$(dirname "$f")"
        if [[ "$parent_dir" == *.framework ]] || [[ "$parent_dir" == *.framework/Versions/* ]] \
            || [[ "$parent_dir" == *.bundle ]] || [[ "$parent_dir" == *.plugin ]]; then
            echo "  Skipping bundle binary (signed in Step 2): $f"
            continue
        fi
        sign_binary "$f"
    done < <(find "dist/${APP_NAME}.app" -type f \
        | xargs file \
        | grep "Mach-O" \
        | cut -d: -f1 \
        | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-)

    # Step 2: Sign bundle directories (.framework, .bundle, .plugin) after their contents.
    # Deepest bundles first (sort by path length descending) to maintain inside-out order.
    # .bundle/.plugin coverage prevents missing CodeResources catalog seals that can
    # trigger notarytool bundle-integrity warnings.
    echo "  Signing bundle directories (.framework, .bundle, .plugin)..."
    while IFS= read -r fw; do
        # PyInstaller-embedded frameworks (e.g. Python.framework inside aw-watcher-window)
        # lack the standard Versions/ structure and Info.plist, so codesign rejects them
        # with "bundle format is ambiguous (could be app or framework)". Fall back to
        # signing the main binary inside the framework directly. All other signing errors
        # are still fatal.
        sign_output=$(codesign --force --options runtime --timestamp \
            --entitlements "$ENTITLEMENTS" \
            --sign "$APPLE_PERSONALID" \
            "$fw" 2>&1) && echo "  Signed bundle: $fw" || {
            if echo "$sign_output" | grep -q "bundle format is ambiguous"; then
                echo "  Note: $fw lacks standard bundle structure; strip-signing and syncing duplicates by content hash"
                # PyInstaller copies Python.framework contents as separate files rather
                # than symlinks — Python, Versions/Current/Python, and Versions/3.9/Python
                # are distinct inodes with identical code but different embedded signatures
                # (different timestamp nonces in __LINKEDIT from PyInstaller's own
                # codesign_identity). After cp -r into the .app, all three paths carry
                # pre-existing but DIFFERENT signatures. A pre-sign SHA comparison
                # never detects them as duplicates, so all three end up signed separately,
                # producing three divergent signatures that Apple rejects as "invalid".
                #
                # Fix: strip all existing signatures first (making copies truly identical
                # at the byte level), then group by content hash, sign one canonical per
                # group via temp copy, and sync the signed result to all group members.
                # This is correct even if the framework contains genuinely different
                # binaries — only true duplicates share a signed payload.
                tmp_group_dir=$(mktemp -d)
                found_macho=false
                while IFS= read -r fw_bin; do
                    found_macho=true
                    existing_id=$(codesign -d "$fw_bin" 2>&1 \
                        | sed -n 's/^Identifier=//p' || true)
                    if [ -z "$existing_id" ]; then
                        existing_id="$(basename "$fw_bin")"
                    fi

                    # Strip any existing signature (from PyInstaller or prior attempts)
                    # so content hashing identifies true duplicates rather than
                    # nonce-only signature differences from previous signing steps.
                    codesign --remove-signature "$fw_bin" 2>/dev/null || true
                    content_hash=$(shasum -a 256 "$fw_bin" | awk '{print $1}')
                    canonical_path_file="$tmp_group_dir/$content_hash.path"

                    if [ -f "$canonical_path_file" ]; then
                        # Same binary content — sync signed payload from canonical.
                        canonical="$canonical_path_file"
                        echo "    Syncing signed binary to duplicate: $fw_bin"
                        cp "$canonical" "$fw_bin"
                    else
                        # First occurrence of this content — sign it as canonical.
                        echo "    Signing canonical binary: $fw_bin (identifier: $existing_id, hash: ${content_hash:0:12})"
                        tmp_binary=$(mktemp)
                        cp -p "$fw_bin" "$tmp_binary"
                        codesign --force --options runtime --timestamp \
                            --entitlements "$ENTITLEMENTS" \
                            --identifier "$existing_id" \
                            --sign "$APPLE_PERSONALID" \
                            "$tmp_binary" || { rm -f "$tmp_binary"; rm -rf "$tmp_group_dir"; exit 1; }
                        cp "$tmp_binary" "$fw_bin"
                        # Save signed canonical as the source for duplicates.
                        cp "$tmp_binary" "$canonical_path_file"
                        rm -f "$tmp_binary"
                    fi
                done < <(find "$fw" -type f | xargs file | grep "Mach-O" | cut -d: -f1 | sort)
                rm -rf "$tmp_group_dir"
                if ! $found_macho; then
                    echo "ERROR: No Mach-O binaries found inside $fw" >&2
                    exit 1
                fi
            else
                echo "ERROR: Failed to sign $fw: $sign_output" >&2
                exit 1
            fi
        }
    done < <(find "dist/${APP_NAME}.app" -type d \
        \( -name "*.framework" -o -name "*.bundle" -o -name "*.plugin" \) \
        | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-)

    # Step 3: Sign the top-level .app bundle last.
    echo "  Signing top-level .app bundle..."
    sign_binary "dist/${APP_NAME}.app"

    echo "App signing complete."
else
    echo "APPLE_PERSONALID not set. Skipping code signing."
fi

echo "App bundle created at: dist/${APP_NAME}.app"
