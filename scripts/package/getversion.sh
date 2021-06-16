#!/bin/bash

# set -e

if [[ $TRAVIS_TAG ]]; then
    _version=$TRAVIS_TAG;
elif [[ $APPVEYOR_REPO_TAG_NAME ]]; then
    _version=$APPVEYOR_REPO_TAG_NAME;
else
    # Exact
    _version=$(git describe --tags --abbrev=0 --exact-match 2>/dev/null)
    if [[ -z $_version ]]; then
        # Latest tag + commit ID
        _version="$(git describe --tags --abbrev=0).dev-$(git rev-parse --short HEAD)"
    fi
fi

echo $_version;
