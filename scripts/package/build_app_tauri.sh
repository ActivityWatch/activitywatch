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
                echo "  Note: $fw lacks standard bundle structure; signing all Mach-O binaries inside via temp copy"
                # PyInstaller copies Python.framework contents as separate files rather
                # than symlinks — Python, Versions/Current/Python, and Versions/3.9/Python
                # are distinct inodes. Signing only $fw_name leaves the Versions/ copies
                # unsigned, causing Apple notarization to reject every affected watcher.
                # Sign every Mach-O file inside the framework via a temp-path copy to
                # avoid the in-place "bundle format is ambiguous" error from codesign.
                signed_count=0
                while IFS= read -r fw_bin; do
                    echo "    Signing framework binary via temp copy: $fw_bin"
                    # Preserve the binary's existing code-signing identifier.
                    # Without --identifier, codesign uses the random temp filename
                    # (e.g. "tmp.XXXXXX") as the identifier, which makes Apple's
                    # notarization service report "The signature of the binary is
                    # invalid" — even though the certificate chain and code hashes
                    # are valid. Using the original identifier (e.g. "org.python.python"
                    # from PyInstaller's codesign_identity step) or falling back to the
                    # binary's filename avoids this rejection.
                    existing_id=$(codesign -d "$fw_bin" 2>&1 \
                        | awk -F= '/^Identifier=/{print $2; exit}' || true)
                    if [ -z "$existing_id" ]; then
                        existing_id=$(basename "$fw_bin")
                    fi
                    echo "      Using identifier: $existing_id"
                    tmp_binary=$(mktemp)
                    cp "$fw_bin" "$tmp_binary"
                    codesign --force --options runtime --timestamp \
                        --entitlements "$ENTITLEMENTS" \
                        --identifier "$existing_id" \
                        --sign "$APPLE_PERSONALID" \
                        "$tmp_binary" || { rm -f "$tmp_binary"; exit 1; }
                    cp "$tmp_binary" "$fw_bin"
                    rm -f "$tmp_binary"
                    signed_count=$((signed_count + 1))
                done < <(find "$fw" -type f | xargs file | grep "Mach-O" | cut -d: -f1)
                if [ "$signed_count" -eq 0 ]; then
                    echo "ERROR: No Mach-O binaries found inside $fw" >&2
                    exit 1
                fi
                echo "  Signed $signed_count Mach-O binary/binaries inside $fw"
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
