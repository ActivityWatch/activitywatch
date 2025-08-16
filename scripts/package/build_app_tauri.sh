#!/bin/bash
set -e

# Configuration
APP_NAME="ActivityWatch"
BUNDLE_ID="net.activitywatch.ActivityWatch"
VERSION="0.1.0"
ICON_PATH="aw-tauri/src-tauri/icons/icon.icns"

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is designed to run on macOS only."
    exit 1
fi

# Check if dist/activitywatch exists
if [ ! -d "dist/activitywatch" ]; then
    echo "Error: dist/activitywatch directory not found. Please build the project first."
    exit 1
fi

# Check if aw-tauri binary exists
if [ ! -f "dist/activitywatch/aw-tauri" ]; then
    echo "Error: aw-tauri binary not found in dist/activitywatch/"
    exit 1
fi

# Clean previous build
echo "Cleaning previous builds..."
rm -rf "dist/${APP_NAME}.app"
mkdir -p "dist"

# Create app bundle structure
echo "Creating app bundle structure..."
mkdir -p "dist/${APP_NAME}.app/Contents/"{MacOS,Resources}

# Copy aw-tauri as the main executable
echo "Copying aw-tauri as main executable..."
cp "dist/activitywatch/aw-tauri" "dist/${APP_NAME}.app/Contents/MacOS/aw-tauri"
chmod +x "dist/${APP_NAME}.app/Contents/MacOS/aw-tauri"

# Copy all other components to Resources in organized directories
echo "Copying all components to Resources..."
for component in dist/activitywatch/*/; do
    if [ -d "$component" ]; then
        component_name=$(basename "$component")
        echo "  Copying $component_name..."
        mkdir -p "dist/${APP_NAME}.app/Contents/Resources/$component_name"
        cp -r "$component"/* "dist/${APP_NAME}.app/Contents/Resources/$component_name/"
    fi
done

# Make all aw-* executables within Resources executable
echo "Setting executable permissions..."
find "dist/${APP_NAME}.app/Contents/Resources" -type f -name "aw-*" -exec chmod +x {} \;

# Copy app icon
echo "Copying app icon..."
if [ -f "$ICON_PATH" ]; then
    cp "$ICON_PATH" "dist/${APP_NAME}.app/Contents/Resources/icon.icns"
else
    echo "Warning: Icon file not found at $ICON_PATH"
fi

# Create Info.plist
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

# Create PkgInfo file
echo "Creating PkgInfo..."
echo "APPL????" > "dist/${APP_NAME}.app/Contents/PkgInfo"

# Code signing (if APPLE_PERSONALID is set)
if [ -n "$APPLE_PERSONALID" ]; then
    echo "Signing app with identity: $APPLE_PERSONALID"
    codesign --deep --force --sign "$APPLE_PERSONALID" "dist/${APP_NAME}.app"
    echo "App signing complete."
else
    echo "APPLE_PERSONALID environment variable not set. Skipping code signing."
fi

echo ""
echo "✅ App bundle created successfully at: dist/${APP_NAME}.app"
echo ""
echo "App Bundle Structure:"
echo "├── Contents/"
echo "│   ├── MacOS/"
echo "│   │   └── aw-tauri (main executable)"
echo "│   ├── Resources/"
for dir in "dist/${APP_NAME}.app/Contents/Resources/"*/; do
    if [ -d "$dir" ] && [[ $(basename "$dir") == aw-* ]]; then
        component_name=$(basename "$dir")
        echo "│   │   ├── $component_name/"
        # Show the main executable in each component
        main_exec=$(find "$dir" -maxdepth 1 -name "aw-*" -type f 2>/dev/null | head -1)
        if [ -n "$main_exec" ]; then
            exec_name=$(basename "$main_exec")
            echo "│   │   │   ├── $exec_name (executable)"
        fi
        # Show other important files
        other_files=$(find "$dir" -maxdepth 2 -name "*.jxa" -o -name "Python" -o -name "*.dylib" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$other_files" -gt 0 ]; then
            echo "│   │   │   └── ... (+ dependencies & libraries)"
        fi
    fi
done
echo "│   │   └── icon.icns"
echo "│   ├── Info.plist"
echo "│   └── PkgInfo"
echo ""
echo "All executables are properly packaged and accessible by aw-tauri."
echo "To test the app, run: open dist/${APP_NAME}.app"
