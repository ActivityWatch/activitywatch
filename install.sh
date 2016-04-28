#!/bin/bash

git submodule update --init --recursive

FOLDERS="aw-core aw-client aw-server aw-watcher-afk aw-watcher-x11"
for FOLDER in $FOLDERS; do
    cd $FOLDER
    sudo python3 setup.py develop
    cd ..
done
