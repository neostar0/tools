#!/usr/bin/env bash
#
# Install Qt into the qgc4-builder image without the interactive installer.
# Called by internal/docker/Dockerfile-build-linux.
#
# aqtinstall's base gcc_64 package already carries QtWebSockets, QtLocation,
# QtMultimedia, QtSerialPort, QtSpeech and the other modules QGC links
# against; QT_MODULES only needs to add the modules that live outside it
# (QGC needs qtcharts).
set -euo pipefail

QT_VERSION="${QT_VERSION:-5.15.2}"
QT_PATH="${QT_PATH:-/opt/Qt}"
QT_HOST="${QT_HOST:-linux}"
QT_TARGET="${QT_TARGET:-desktop}"
QT_ARCH="${QT_ARCH:-gcc_64}"
QT_MODULES="${QT_MODULES:-qtcharts}"

python3 -m pip install --no-cache-dir --upgrade pip
python3 -m pip install --no-cache-dir aqtinstall

aqt install-qt "${QT_HOST}" "${QT_TARGET}" "${QT_VERSION}" "${QT_ARCH}" \
    --outputdir "${QT_PATH}" \
    --modules "${QT_MODULES}"

echo "Qt ${QT_VERSION} (${QT_ARCH}) installed under ${QT_PATH}/${QT_VERSION}/${QT_ARCH}"
