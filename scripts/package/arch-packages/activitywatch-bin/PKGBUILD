# Maintainer: Erik Bjäreholt <erik.bjareholt@gmail.com>

pkgname=activitywatch-bin
pkgver='0.7.1'
pkgrel=1
epoch=
pkgdesc="Log what you do on your computer. Simple, extensible, no third parties."
arch=('x86_64')
url="https://github.com/ActivityWatch/activitywatch"
license=('MPL2')
provides=("activitywatch")
conflicts=("activitywatch")
source=("https://github.com/ActivityWatch/activitywatch/releases/download/v${pkgver}/activitywatch-v${pkgver}-linux-x86_64.zip")
md5sums=('SKIP')

package() {
    # Install into /opt/activitywatch
    mkdir -p $pkgdir/opt
    cp -r activitywatch $pkgdir/opt

    # Symlink executables to /usr/bin
    mkdir -p $pkgdir/usr/bin
    execnames=("aw-server" "aw-watcher-afk" "aw-watcher-window" "aw-qt")
    for execname in $execnames; do
        ln -s /opt/activitywatch/$execname $pkgdir/usr/bin/$execname
    done
}
