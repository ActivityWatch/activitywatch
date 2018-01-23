#!/bin/bash

# Get current branch
#   git rev-parse --abbrev-ref HEAD
# Get branch for each submodule
#   git submodule foreach "git rev-parse --abbrev-ref HEAD"

SUBMODULES=$(git submodule | sed -r -e 's/^[ \+][a-z0-9]+ //g' -e 's/ \(.*\)//g')
for module in $SUBMODULES; do
    branch=$(git --git-dir=$module/.git rev-parse --abbrev-ref HEAD)
    printf "%-20s %-30s\n" "$module" "$branch"
done
