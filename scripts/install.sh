#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SETUP_ARGS=""

which python3
python3 -V

function install_package() {
    echo "Installing $(pwd)"
    python3 setup.py develop $SETUP_ARGS
}

if [[ $1 == '--user' ]]; then
    SETUP_ARGS="$SETUP_ARGS --user"
    echo "Installing as user"
fi

cd "$DIR/.."
PYSETUPS=$(find . -maxdepth 2 | egrep 'setup.py')
for PYSETUP in $PYSETUPS; do
    FOLDER=$(dirname $PYSETUP)
    cd $FOLDER
    install_package
    cd ..
done
