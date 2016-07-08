#!/bin/bash
# Pull this repo
git pull
# Pull other git modules
git submodule update --init --recursive

while getopts "a" opt; do
    case $opt in
        a)
            # Pull bleeding edge from submodules
            FOLDERS="aw-*"
            for FOLDER in $FOLDERS; do
                pushd $FOLDER
                git checkout master
                git pull
                popd
            done
			;;
		\?)
			echo "Invalid flag"
			;;
	esac
done
