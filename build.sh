#!/bin/bash

#
# NOTE: Highly WIP!
#

PYINSTALL_TARGETS=$(find -maxdepth 2 | egrep 'aw-.*/.*\.spec')

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
    pyinstaller $target --onefile --clean || echo "Failed to build $target" && exit 1
done

echo
echo "-------------------------------------"
echo "Contents of ./dist"
ls -l dist
echo "-------------------------------------"

