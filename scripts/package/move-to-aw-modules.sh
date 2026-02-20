#!/usr/bin/bash

EXCLUDES="--exclude=aw-tauri --exclude=aw-server-rust --exclude=awatcher --exclude=move-to-aw-modules.sh --exclude=README.txt"

if [[ -n "$XDG_SESSION_TYPE" && "$XDG_SESSION_TYPE" == "wayland" ]]; then
    rsync -a . ~/aw-modules/ $EXCLUDES
    cp ./awatcher/aw-awatcher ~/aw-modules/
else
    rsync -a . ~/aw-modules/ $EXCLUDES
fi
cp aw-server-rust/aw-sync ~/aw-modules/
