#!/bin/bash

set -e

# Clean
rm -r dist/
mkdir dist
mkdir dist/activitywatch

PYINSTALL_TARGETS=$(find . -maxdepth 2 | egrep 'aw-.*/.*\.spec')

echo "PyInstaller .spec files found"
for target in $PYINSTALL_TARGETS; do
    echo " - $target";
done

for target in $PYINSTALL_TARGETS; do
    target_dir=$(dirname $target)

    echo
    echo "-------------------------------------"
    echo "Building $target_dir"
    pyinstaller $target --clean

    # Putting it all in one folder
    cp -r dist/$target_dir/* dist/activitywatch
    rm -r dist/$target_dir
done

echo
echo "-------------------------------------"
echo "Zipping executables..."
cd dist;
platform=$(uname | tr '[:upper:]' '[:lower:]')
if [[ "$platform" == "darwin" ]]; then
    platform="macos";
elif [[ $platform == "cygwin"* ]]; then
    platform="windows"
fi
zip -r "activitywatch-${platform}.zip" activitywatch;
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

