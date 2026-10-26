#!/usr/bin/env bash

# Install the Qt for Android kit used by qgc-android-builder. aqt installs all
# Android ABIs (arm64-v8a, armeabi-v7a, x86, x86_64) into the same tree.
set -e

QT_VERSION="${QT_VERSION:-5.15.2}"
QT_PATH="${QT_PATH:-/opt/Qt}"
QT_HOST="${QT_HOST:-linux}"
QT_TARGET="${QT_TARGET:-android}"
QT_MODULES="${QT_MODULES:-qtcharts}"

apt-get update
apt-get install -y --no-install-recommends python3 python3-pip
pip3 install --no-cache-dir aqtinstall
aqt install-qt "${QT_HOST}" "${QT_TARGET}" "${QT_VERSION}" -O "${QT_PATH}" -m "${QT_MODULES}"
echo "Qt for Android installed under ${QT_PATH}/${QT_VERSION}/android"
