#!/bin/bash

set -e

echo "-------------------------------------"
echo "Zipping executables..."
cd dist;

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
    elif [[ $_platform == "cygwin"* ]]; then
        echo "ERROR: cygwin is not a valid platform";
        exit 1;
    fi

    echo $_platform;
}

function get_version() {
    if [[ $TRAVIS_TAG ]]; then
        _version=$TRAVIS_TAG;
    elif [[ $APPVEYOR_REPO_TAG_NAME ]]; then
        _version=$APPVEYOR_REPO_TAG_NAME;
    else
        _version=$(git rev-parse --short HEAD)
    fi

    echo $_version;
}

function get_arch() {
    _arch="$(uname -m)"
    echo $_arch;
}

platform=$(get_platform)
version=$(get_version)
arch=$(get_arch)

echo "Platform: $platform, arch: $arch, version: $version"

zipname="activitywatch-${platform}-${arch}-${version}.zip"
echo "Name of package will be: $zipname"

if [[ $platform == "windows"* ]]; then
    7z a $zipname activitywatch;
else
    zip -r $zipname activitywatch;
fi
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

