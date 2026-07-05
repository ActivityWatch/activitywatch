#!/bin/bash

# pip removed --format=legacy in 23.0 (2023-01-30); use --format=freeze which
# outputs `aw-core==0.5.x` and is stable across pip versions.
modules=$(pip3 list --format=freeze | grep '^aw-' | grep -o '^aw-[^=]*')

for module in $modules; do
    pip3 uninstall -y $module
done
