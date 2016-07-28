#!/bin/bash
for module in "aw-server" "aw-watcher-afk" "aw-watcher-x11"; do
    ln -s $(pwd)/$module/misc/${module}.service ~/.config/systemd/user/${module}.service
done
