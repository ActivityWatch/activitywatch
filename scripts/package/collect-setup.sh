#!/bin/bash

set -e

# The Research Edition patcher rewrites OutputBaseFilename in the .iss
# (activitywatch-research[-tauri]-setup), so resolve the produced file
# instead of hardcoding the standard name. dist/ is fresh at this point,
# so exactly one setup exe must exist.
setup_src=(dist/activitywatch*-setup.exe)
if [ ${#setup_src[@]} -ne 1 ] || [ ! -f "${setup_src[0]}" ]; then
    echo "ERROR: expected exactly one dist/activitywatch*-setup.exe, got: ${setup_src[*]}"
    exit 1
fi
mv "${setup_src[0]}" "dist/$1"
