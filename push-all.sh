#!/bin/bash

FOLDERS="aw-*"
for FOLDER in $FOLDERS; do
    cd $FOLDER
    echo "Pushing $FOLDER..."
    git push
    cd ..
    echo
done
