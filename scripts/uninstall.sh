#!/bin/bash

modules=$(pip3 list --format=legacy | grep 'aw-' | grep -o '^aw-[^ ]*')

for module in $modules; do
    pip3 uninstall -y $module
done

