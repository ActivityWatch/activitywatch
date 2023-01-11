#!/bin/bash

# Update dependency locks for each submodule in the activitywatch repo

set -e
set -x

# For submodule in submodules:
for submodule in $(git submodule | sed 's/^[+ ]//' | cut -d' ' -f2); do
    # Go to submodule
    cd $submodule

    # Check that we're on the master branch and latest commit
    if [ $(git rev-parse --abbrev-ref HEAD) != "master" ]; then
        echo "Submodule $submodule is not on master branch, aborting"
        exit 1
    fi

    # Update dependency locks
    # Use poetry if poetry.lock exists, or cargo if Cargo.toml exists
    if [ -f "poetry.lock" ]; then
        poetry update
    elif [ -f "Cargo.toml" ]; then
        cargo update
    fi

    # Go back to root
    cd ..
done

