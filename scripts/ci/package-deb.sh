set -e

VERSION_NUM=$(scripts/package/getversion.sh)
echo $VERSION_NUM
PKGDIR="activitywatch_$VERSION_NUM"

# Package tools
sudo apt install sed jdupes wget

if [ -d "PKGDIR" ]; then
    sudo rm -rf $PKGDIR
fi

