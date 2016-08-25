#!/bin/bash

#
# NOTE: Highly WIP!
#

function build_fail {
    echo "Failed to build $1"
    exit 1
}

# Clean
rm -r dist/
mkdir dist
mkdir dist/activitywatch

#
# Build Web UI
#

cd aw-webui
npm install || build_fail
npm run build || build_fail
cd ..
cp -r aw-webui/dist aw-server/aw_server/static || build_fail


#
# PyInstaller
#


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
    pyinstaller $target --clean || build_fail

    # Putting it all in one folder
    cp -r dist/$target_dir/* dist/activitywatch || build_fail
    rm -r dist/$target_dir
done

echo
echo "-------------------------------------"
echo "Zipping executables..."
cd dist;
platform=$(uname | tr '[:upper:]' '[:lower:]')
if [[ "$platform" == "darwin" ]]; then
    platform="macos";
fi
zip -r "activitywatch-${platform}.zip" activitywatch;
cd ..;
echo "-------------------------------------"

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

