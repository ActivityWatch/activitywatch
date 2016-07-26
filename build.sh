#!/bin/bash

#
# NOTE: Highly WIP!
#

PYINSTALL_TARGETS=$(find -maxdepth 2 | egrep 'aw-.*/.*\.spec')

for target in $PYINSTALL_TARGETS; do
    pyinstaller $target
done
