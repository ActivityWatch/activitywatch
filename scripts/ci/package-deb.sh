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

