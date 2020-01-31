#!/bin/bash

set -e

if [[ $TRAVIS_TAG ]]; then
    _version=$TRAVIS_TAG;
elif [[ $APPVEYOR_REPO_TAG_NAME ]]; then
    _version=$APPVEYOR_REPO_TAG_NAME;
else
    _version=$(git rev-parse --short HEAD)
fi

echo $_version;
