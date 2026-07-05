#!/bin/bash

modules=$(pip3 list --format=freeze | grep '^aw-' | cut -d'=' -f1)

for module in $modules; do
    pip3 uninstall -y $module
done

