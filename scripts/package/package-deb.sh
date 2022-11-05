#!/usr/bin/bash
# Setting the shell is required, as `sh` doesn't support slicing.

# Fail fast
set -e
# Verbose commands for CI verification
set -x

VERSION=$(scripts/package/getversion.sh)
# Slice off the "v" from the tag, which is probably guaranteed
VERSION_NUM=${VERSION:1}
echo $VERSION_NUM
PKGDIR="activitywatch_$VERSION_NUM"

# Package tools
sudo apt-get install sed jdupes wget

if [ -d "PKGDIR" ]; then
    sudo rm -rf $PKGDIR
fi

# .deb meta files
mkdir -p $PKGDIR/DEBIAN
# activitywatch's install location
mkdir -p $PKGDIR/opt
# Allows aw-qt to autostart.
mkdir -p $PKGDIR/etc/xdg/autostart
# Allows users to manually start aw-qt from their start menu.
mkdir -p $PKGDIR/usr/share/applications

# While storing the control file in a variable here, dumping it in a file is so unnecessarily
# complicated that it's easier to just dump move and sed.
cp ./scripts/package/deb/control $PKGDIR/DEBIAN/control
sed -i "s/SCRIPT_VERSION_HERE/${VERSION_NUM}/" $PKGDIR/DEBIAN/control

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
sudo cp $PKGDIR/opt/activitywatch/aw-qt.desktop $PKGDIR/etc/xdg/autostart/
sudo cp $PKGDIR/opt/activitywatch/aw-qt.desktop $PKGDIR/usr/share/applications/

dpkg-deb --build $PKGDIR
sudo mv activitywatch_${VERSION_NUM}.deb dist/activitywatch-${VERSION}-linux-x86_64.deb
