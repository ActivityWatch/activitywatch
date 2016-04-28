#!/bin/bash

FOLDERS="aw-*"
for FOLDER in $FOLDERS; do
    cd $FOLDER
    git push
    cd ..
done
