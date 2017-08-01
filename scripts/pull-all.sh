#!/bin/bash

echo "WARNING
This will:
 - Pull the bundle repo
 - Pull all the submodules
 - And, if given the -a flag, for each submodule:
   - Checkout the master branch
   - Pull the latest master commit"

read -p "Are you sure? (y/n): " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "As you wish, starting now."
else
    exit 1
fi

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
                echo "Checked out master and pulled for: $FOLDER"
                popd
            done
			;;
		\?)
			echo "Invalid flag"
			;;
	esac
done
