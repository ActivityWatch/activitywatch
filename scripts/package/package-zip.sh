#!/bin/bash

set -e

echo "-------------------------------------"
echo "Zipping executables..."
cd dist;

function get_platform() {
    _platform=$(uname | tr '[:upper:]' '[:lower:]')
    if [[ "$platform" == "darwin" ]]; then
        _platform="macos";
    elif [[ $platform == "msys"* ]]; then
        _platform="windows";
    elif [[ $platform == "cygwin"* ]]; then
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

platform=$(get_platform)
version=$(get_version)

echo "Platform: $platform, version: $version"

if [[ $platform == "windows"* ]]; then
    7z a "activitywatch-${platform}-${version}.zip" activitywatch;
else
    zip -r "activitywatch-${platform}-${version}.zip" activitywatch;
fi
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

