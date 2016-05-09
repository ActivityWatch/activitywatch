#!/bin/bash

git submodule update --init --recursive

function fatal_error() {
    echo "Something went wrong, aborting"
    exit 1
}

FOLDERS="aw-core aw-client aw-server aw-watcher-afk aw-watcher-x11"
for FOLDER in $FOLDERS; do
    cd $FOLDER
    sudo python3 setup.py develop || fatal_error
    cd ..
done
