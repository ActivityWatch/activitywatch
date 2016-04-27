#!/bin/bash

FOLDERS="aw-core aw-client aw-server aw-watcher-afk aw-watcher-x11"

for folder in $FOLDERS; do
    cd $folder
    sudo python3 setup.py develop
    cd ..
done
