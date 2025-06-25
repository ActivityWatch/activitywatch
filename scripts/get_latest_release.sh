#!/bin/bash

# TODO: Merge with scripts/package/getversion.sh

# Script that fetches the previous release (if current commit is a tag),
# or the latest release, if current commit is not a tag.

# If stable only, then we return the latest stable release, 
# else, we will return the latest release, either stable or prerelease.
RE_STABLE='(?<=[/])v[0-9\.]+$'
RE_INCL_PRERELEASE='(?<=[/])v[0-9\.]+(a|b|rc)?[0-9]+$'

# Get tag for this commit, if any
TAG=$(git describe --tags --exact-match 2>/dev/null)

RE=$RE_INCL_PRERELEASE
if [ -n "$STABLE_ONLY" ]; then
    if [ "$STABLE_ONLY" = "true" ]; then
        RE=$RE_STABLE
    fi
fi
ALL_TAGS=`git for-each-ref --sort=creatordate --format '%(refname)' refs/tags`

# If current commit is a tag, we filter it out
if [ -n "$TAG" ]; then
    ALL_TAGS=`echo "$ALL_TAGS" | grep -v "^refs/tags/$TAG$"`
fi

echo "$ALL_TAGS" | grep -P "$RE" --only-matching | tail -n1
