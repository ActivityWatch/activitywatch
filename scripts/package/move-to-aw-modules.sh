#!/usr/bin/bash

if [[ -n "$XDG_SESSION_TYPE" && "$XDG_SESSION_TYPE" == "wayland" ]]; then
    rsync -a . ~/aw-modules/ --exclude=aw-tauri --exclude=aw-server-rust --exclude=awatcher --exclude=move-to-aw-modules.sh --exclude=README.txt
    cp ./awatcher/aw-awatcher ~/aw-modules/
    cp aw-server-rust/aw-sync ~/aw-modules/
else 
    rsync -r . ~/aw-modules/ --exclude=aw-tauri --exclude=awatcher \
    --exclude=aw-server-rust --exclude=move-to-aw-modules.sh --exclude=README.txt
    
    cp aw-server-rust/aw-sync ~/aw-modules
fi
