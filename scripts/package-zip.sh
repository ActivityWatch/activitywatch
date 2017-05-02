#!/bin/bash

set -e

echo "-------------------------------------"
echo "Zipping executables..."
cd dist;
platform=$(uname | tr '[:upper:]' '[:lower:]')
if [[ "$platform" == "darwin" ]]; then
    platform="macos";
elif [[ $platform == "msys"* ]]; then
    platform="windows"
elif [[ $platform == "cygwin"* ]]; then
    echo "ERROR: cygwin is not a valid platform"
    exit 1
fi

echo "Platform is: $platform"

if [[ $platform == "windows"* ]]; then
    7z a "activitywatch-${platform}.zip" activitywatch;
else
    zip -r "activitywatch-${platform}.zip" activitywatch;
fi
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

