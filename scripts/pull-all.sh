#!/bin/bash
# Pull this repo
git pull
# Pull other git modules
git submodule update --init --recursive

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

while getopts "a" opt; do
    case $opt in
        a)
            # Pull bleeding edge from submodules
            FOLDERS="$DIR/../aw-*"
            for FOLDER in $FOLDERS; do
                pushd $FOLDER
                git checkout master
                git pull origin master
                popd
            done
			;;
		\?)
			echo "Invalid flag"
			;;
	esac
done
