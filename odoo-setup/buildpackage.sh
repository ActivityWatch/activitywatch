#!/usr/bin/bash
set -xe

cd "$(dirname "$(realpath "$0")")" || exit

DISTRO_NAME="${1:-${DISTRO_NAME:-"noble"}}"
PACKAGE_NAME="${2:-${PACKAGE_NAME:-"activitywatch-odoo-$DISTRO_NAME"}}"

DOCKER_FILE="Dockerfile_${DISTRO_NAME}"
DOCKER_TAG="${DISTRO_NAME}-awbuilder"

docker build -t "${DOCKER_TAG}" . -f "${DOCKER_FILE}" --build-arg=USID=$(id -u) --build-arg=GRID=$(id -g)

DEBUILD_PATH="/data/build/dist/${PACKAGE_NAME}"

docker run --rm -v ../:/data/build/activitywatch -v ./dist:/data/build/dist -t "${DOCKER_TAG}:latest" \
	/bin/bash -c \
	"cd /data/build/activitywatch \
	&& mkdir -p ${DEBUILD_PATH} \
    && rm -rf ${DEBUILD_PATH}/* \
	&& make clean \
	&& make build SUBMODULES='aw-core aw-client aw-qt aw-server aw-server-rust aw-watcher-afk aw-watcher-window awatcher' \
	&& make package SUBMODULES='aw-core aw-client aw-qt aw-server aw-server-rust aw-watcher-afk aw-watcher-window awatcher' \
    && unzip /data/build/activitywatch/dist/activitywatch-*-linux-x86_64.zip -d ${DEBUILD_PATH}/opt/ \
    && echo 'Preparing Debian Package' \
    && cd ${DEBUILD_PATH} \
    && cp -rav /data/build/activitywatch/odoo-setup/debian DEBIAN \
    && mkdir -p usr/share/gnome-shell/extensions/ \
	&& unzip /data/build/activitywatch/odoo-setup/focused-window-dbus-${DISTRO_NAME}.zip -d usr/share/gnome-shell/extensions/ \
	&& cp /data/build/activitywatch/odoo-setup/aw-systray-odoo.py opt/activitywatch/aw-systray-odoo.py \
	&& mkdir -p etc/xdg/autostart/ \
	&& mkdir -p usr/share/applications/ \
	&& cp /data/build/activitywatch/odoo-setup/activitywatch-odoo.desktop etc/xdg/autostart/ \
	&& cp /data/build/activitywatch/odoo-setup/activitywatch-odoo.desktop usr/share/applications/ \
	&& echo 'Building Debian Package' \
    && cd /data/build/dist \
	&& dpkg-deb --root-owner-group -Zxz --build ${PACKAGE_NAME}"
