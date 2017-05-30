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
    elif [[ $_platform == "cygwin"* ]]; then
        echo "ERROR: cygwin is not a valid platform";
        exit 1;
    fi

    echo $_platform;
}

function get_version() {
    if [[ $TRAVIS_VERSION ]]; then
        _version=$TRAVIS_VERSION;
    elif [[ $APPVEYOR_REPO_TAG_NAME ]]; then
        _version=$APPVEYOR_REPO_TAG_NAME;
    else
        _version=$(git rev-parse --short HEAD)
    fi

    echo $_version;
}

function get_arch() {
    _platform=$(get_platform)
    if [[ $_platform == "linux" || $_platform == "macos" ]]; then
        _arch="$(uname -m)"
    elif [[ $PYTHON_ARCH ]]; then
        # $PYTHON_ARCH is set on appveyor
        if [[ $PYTHON_ARCH == "64" ]]; then
            _arch="x86_64"
        elif [[ $PYTHON_ARCH == "32" ]]; then
            _arch="x86"
        else
            echo "invalid arch"
            exit 1
        fi
    else
        _arch="unknown_arch"
    fi

    echo $_arch;
}

platform=$(get_platform)
version=$(get_version)
arch=$(get_arch)

echo "Platform: $platform, arch: $arch, version: $version"

zipname="activitywatch-${platform}-${arch}-${version}.zip"
echo "Name of package will be: $zip"

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

