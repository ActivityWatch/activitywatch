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

# TODO: Detect folders, don't require a definition of them
FOLDERS="aw-core aw-client aw-server aw-watcher-afk aw-watcher-window aw-qt"
cd "$DIR/.."
for FOLDER in $FOLDERS; do
    cd $FOLDER
    install_package
    cd ..
done
