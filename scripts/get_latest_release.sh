#!/bin/bash

# Script that fetches the previous release (if current commit is a tag),
# or the latest release, if current commit is not a tag.

# If not stable only, then we return either the latest prerelease, or if none, the latest stable release
RE='(?<=[/])v[0-9\.]+(a|b|rc)[0-9]+$'

# Get tag for this commit, if any
TAG=$(git describe --tags --exact-match 2>/dev/null)

if [ -n "$STABLE_ONLY" ]; then
    if [ "$STABLE_ONLY" = "true" ]; then
        # If stable only, then we only want to return the latest stable version
        RE='(?<=[/])v[0-9\.]+$'
    fi
fi
ALL_TAGS=`git for-each-ref --sort=creatordate --format '%(refname)' refs/tags`

# If current commit is a tag, we filter it out
if [ -n "$TAG" ]; then
    ALL_TAGS=`echo "$ALL_TAGS" | grep -v "^refs/tags/$TAG$"`
fi

echo "$ALL_TAGS" | grep -P "$RE" --only-matching | tail -n1
