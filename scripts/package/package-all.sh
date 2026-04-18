#!/bin/bash

set -e

echoerr() { echo "$@" 1>&2; }

function get_platform() {
    # Will return "linux" for GNU/Linux
    #   I'd just like to interject for a moment...
    #   https://wiki.installgentoo.com/index.php/Interjection
    # Will return "macos" for macOS/OS X
    # Will return "windows" for Windows/MinGW/msys

    _platform=$(uname | tr '[:upper:]' '[:lower:]')
    if [[ $_platform == "darwin" ]]; then
        _platform="macos";
    elif [[ $_platform == "msys"* ]]; then
        _platform="windows";
    elif [[ $_platform == "mingw"* ]]; then
        _platform="windows";
    elif [[ $_platform == "linux" ]]; then
        # Nothing to do
        true;
    else
        echoerr "ERROR: $_platform is not a valid platform";
        exit 1;
    fi

    echo $_platform;
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function get_version() {
    "$SCRIPT_DIR/getversion.sh";
}

function get_version_no_prefix() {
    "$SCRIPT_DIR/getversion.sh" --strip-v;
}

function get_arch() {
    _arch="$(uname -m)"
    echo $_arch;
}

platform=$(get_platform)
version=$(get_version)
version_no_prefix=$(get_version_no_prefix)
arch=$(get_arch)
build_suffix=""
if [[ $TAURI_BUILD == "true" ]]; then
    build_suffix="-tauri"
fi

echo "========================================"
echo "Build Version Information"
echo "========================================"
echo "Platform:       $platform"
echo "Arch:           $arch"
echo "Version (with v):  $version"
echo "Version (no v):     $version_no_prefix"
echo "Tauri build:    ${TAURI_BUILD:-false}"
echo "========================================"
echo

# For Tauri Linux builds, include helper scripts and README
if [[ $platform == "linux" && $TAURI_BUILD == "true" ]]; then
    cp scripts/package/README.txt scripts/package/move-to-aw-modules.sh dist/activitywatch/
fi

function build_zip() {
    echo "Zipping executables..."
    pushd dist;
    filename="activitywatch${build_suffix}-${version}-${platform}-${arch}.zip"
    echo "Name of package will be: $filename"

    if [[ $platform == "windows"* ]]; then
        7z a $filename activitywatch;
    else
        zip -r $filename activitywatch;
    fi
    popd;
    echo "Zip built!"
}

function build_setup() {
    filename="activitywatch${build_suffix}-${version}-${platform}-${arch}-setup.exe"
    echo "Name of package will be: $filename"

    innosetupdir="/c/Program Files (x86)/Inno Setup 6"
    if [ ! -d "$innosetupdir" ]; then
        echo "ERROR: Couldn't find innosetup which is needed to build the installer. We suggest you install it using chocolatey. Exiting."
        exit 1
    fi

    if [[ $TAURI_BUILD == "true" ]]; then
        env AW_VERSION=$version_no_prefix "$innosetupdir/iscc.exe" scripts/package/aw-tauri.iss
    else
        env AW_VERSION=$version_no_prefix "$innosetupdir/iscc.exe" scripts/package/activitywatch-setup.iss
    fi
    mv dist/activitywatch-setup.exe dist/$filename
    echo "Setup built!"
}

build_zip
if [[ $platform == "windows"* ]]; then
    build_setup
fi

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

