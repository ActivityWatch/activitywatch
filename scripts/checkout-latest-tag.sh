#!/bin/bash

latest_version_tag=$(git tag -l | grep "^v[0-9]\..*" | sort --version-sort | tail -n1 )
current_version_tag=$(git describe --tags)
echo "Latest version: $latest_version_tag"
echo "Current version: $current_version_tag"
