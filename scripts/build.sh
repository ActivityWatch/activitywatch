#!/bin/bash

set -e

#
# Build Web UI
#

make --directory=aw-webui
cp -r aw-webui/dist/* aw-server/aw_server/static/

#
# Build aw-qt's resources.py with pyrcc
#

cd aw-qt
./build.sh
cd ..
