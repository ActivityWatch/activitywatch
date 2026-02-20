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
    echo "Signing app with identity: $APPLE_PERSONALID"
    codesign --deep --force --sign "$APPLE_PERSONALID" "dist/${APP_NAME}.app"
    echo "App signing complete."
else
    echo "APPLE_PERSONALID not set. Skipping code signing."
fi

echo "App bundle created at: dist/${APP_NAME}.app"
