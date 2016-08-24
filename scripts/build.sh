#!/bin/bash

#
# NOTE: Highly WIP!
#

PYINSTALL_TARGETS=$(find . -maxdepth 2 | egrep 'aw-.*/.*\.spec')

function build_fail {
    echo "Failed to build $1"
    exit 1
}

echo "PyInstaller .spec files found"
for target in $PYINSTALL_TARGETS; do
    echo " - $target";
done
rm -rf dist build

for target in $PYINSTALL_TARGETS; do
    target_dir=$(dirname $target)

    echo
    echo "-------------------------------------"
    echo "Building $target_dir"
    pyinstaller $target --onefile --clean || build_fail
done

echo
echo "-------------------------------------"
echo "Zipping executables..."
cd dist;
platform=$(uname | tr '[:upper:]' '[:lower:]')
if [[ "$platform" == "darwin" ]]; then
    platform="macos";
fi
zip "activitywatch-${platform}.zip" aw-*;
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

