#!/bin/bash
# Pull this repo
git pull
# Pull other git modules
git submodule update --init --recursive

while getopts "a" opt; do
    case $opt in
        a)
            # Pull bleeding edge from submodules
            dirname="$(dirname $0)/.."
            folders=$(ls "$dirname" | grep "aw-*")
            for folder in $folders; do
                pushd $folder
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
