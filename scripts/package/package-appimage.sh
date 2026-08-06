#!/bin/bash

# pick the latest zip
# NOTE: this assumes that the latest built zip is the only zip in the directory
ZIP_FILE=`ls ./dist/ -1 | grep zip | sort -r | head -1`
unzip ./dist/$ZIP_FILE

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
# Deliberately unversioned: the AppImage has kept this exact name across
# releases so the stable download URL keeps working, e.g.
# https://github.com/ActivityWatch/activitywatch/releases/latest/download/activitywatch-linux-x86_64.AppImage
EDITION=""
if [[ $AW_RESEARCH_EDITION == "true" ]]; then
    EDITION="-research"
fi
cp -v $APPIMAGE_FILE ./dist/activitywatch${EDITION}-linux-x86_64.AppImage
