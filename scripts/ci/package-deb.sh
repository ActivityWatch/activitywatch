set -e

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

# DEBIAN/control metafile. Could make this an explicit file, but 
# keeping it here opens for shoving VERSION_NUM directly in as a
# variable.
# It's a convenience. Nothing more, nothing less.
debianControlFile="Package: activitywatch
Architecture: amd64
Maintainer: Erik Bjäreholt <erik@bjareho.lt>
Depends:
Priority: optional
Version: ${VERSION_NUM}
Description: Open source time tracker
 https://github.com/ActivityWatch/activitywatch"

echo $debianControlFile > $PKGDIR/DEBIAN/control
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
