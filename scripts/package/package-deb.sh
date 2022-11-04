#!/usr/bin/bash

set -e
# Verbose commands for CI verification
set -x

VERSION=$(scripts/package/getversion.sh)
# Slice off the "v" from the tag, which is probably guaranteed
VERSION_NUM=${VERSION:1}
echo $VERSION_NUM
PKGDIR="activitywatch_$VERSION_NUM"

# Package tools
sudo apt install sed jdupes wget

if [ -d "PKGDIR" ]; then
    sudo rm -rf $PKGDIR
fi

mkdir -p $PKGDIR/DEBIAN
mkdir -p $PKGDIR/opt
mkdir -p $PKGDIR/etc/xdg/autostart

# While storing the control file in a variable here, dumping it in a file is so unnecessarily
# complicated that it's easier to just dump move and sed.
cp ./scripts/package/deb/control $PKGDIR/DEBIAN/control
sed -i "s/SCRIPT_VERSION_HERE/${VERSION}/" $PKGDIR/DEBIAN/control

# Verify the file content
cat $PKGDIR/DEBIAN/control
# The entire opt directory (should) consist of dist/activitywatch/*

cp -r dist/activitywatch/ $PKGDIR/opt/

# Hard link duplicated libraries
# (I have no idea what this is for)
jdupes -L -r -S -Xsize-:1K $PKGDIR/opt/

sudo chown -R root:root $PKGDIR

# Prepare the .desktop file
sudo sed -i 's!Exec=aw-qt!Exec=/opt/activitywatch/aw-qt!' $PKGDIR/opt/activitywatch/aw-qt.desktop
sudo cp $PKGDIR/opt/activitywatch/aw-qt.desktop $PKGDIR/etc/xdg/autostart

dpkg-deb --build $PKGDIR
