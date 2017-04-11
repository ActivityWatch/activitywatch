#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

function install_package() {
    echo "Installing $(pwd)"
    if [[ $NOROOT_INSTALL ]]; then
        env python setup.py develop --user
    else
        sudo env python setup.py develop --user
    fi
}

if [[ $1 == '--noroot' ]]; then
    NOROOT_INSTALL=true
    echo "Installing without root"
fi

cd "$DIR/.."
PYSETUPS=$(find . -maxdepth 2 | egrep 'setup.py')
for PYSETUP in $PYSETUPS; do
    FOLDER=$(dirname $PYSETUP)
    cd $FOLDER
    install_package
    cd ..
done
