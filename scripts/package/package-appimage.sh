#!/bin/bash

# pick the latest zip
# NOTE: this assumes that the latest built zip is the only zip in the directory
ZIP_FILE=`ls ./dist/ -1 | grep zip | sort -r | head -1`
unzip ./dist/$ZIP_FILE

# Remove the bundled libwayland-client so the host's copy is used instead.
# The bundled one is older than the bundled Qt Wayland plugin, which made
# aw-qt crash on startup on newer distros with:
#   libQt6WaylandClient.so.6: undefined symbol: wl_proxy_marshal_flags
# (wl_proxy_marshal_flags was added in libwayland 1.20). libwayland-client is
# meant to come from the host anyway, so dropping it from the bundle is safe.
# See https://github.com/ActivityWatch/activitywatch/issues/939
find activitywatch -name 'libwayland-client.so*' -delete

# fetch deps
wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x linuxdeploy-x86_64.AppImage
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

# create AppRun
echo '#!/bin/sh
DIR="$(dirname "$(readlink -f "${0}")")"
"${DIR}"/aw-qt "$@"' > activitywatch/AppRun
chmod a+x ./activitywatch/AppRun

# build appimage
./linuxdeploy-x86_64.AppImage --appdir activitywatch --executable ./activitywatch/aw-qt --output appimage --desktop-file ./activitywatch/aw-qt.desktop --icon-file ./activitywatch/media/logo/logo.png --icon-filename activitywatch
APPIMAGE_FILE=`ls -1 | grep AppImage| grep -i ActivityWatch`
cp -v $APPIMAGE_FILE ./dist/activitywatch-linux-x86_64.AppImage
