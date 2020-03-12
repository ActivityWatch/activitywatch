#!/bin/sh
export PREVIOUS_RELEASE_TAG=$(git describe --abbrev=0)
git log $PREVIOUS_RELEASE_TAG...master --oneline --decorate >> commit_summary.txt
git submodule foreach --recursive git submodule summary $PREVIOUS_RELEASE_TAG >> commit_summary.txt
