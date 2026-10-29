#!/usr/bin/env bash

# Install the Qt for Android kit used by qgc-android-builder. aqt installs all
# Android ABIs (arm64-v8a, armeabi-v7a, x86, x86_64) into the same tree.
set -e

QT_VERSION="${QT_VERSION:-5.15.2}"
QT_PATH="${QT_PATH:-/opt/Qt}"
QT_HOST="${QT_HOST:-linux}"
QT_TARGET="${QT_TARGET:-android}"
QT_MODULES="${QT_MODULES:-qtcharts}"
AQT_ATTEMPTS="${AQT_ATTEMPTS:-5}"
AQT_RETRY_DELAY="${AQT_RETRY_DELAY:-5}"

apt-get update
apt-get install -y --no-install-recommends python3 python3-pip
pip3 install --no-cache-dir aqtinstall

# aqt fetches each module from download.qt.io and its fallback mirrors. A single
# mirror can have a broken TLS certificate or a transient network error (seen
# with ftp2.nluug.nl), which aborts the whole install. Retry so one bad mirror
# does not fail the Docker image build; aqt reuses already downloaded archives.
attempt=1
until aqt install-qt "${QT_HOST}" "${QT_TARGET}" "${QT_VERSION}" -O "${QT_PATH}" -m "${QT_MODULES}"; do
    if [ "${attempt}" -ge "${AQT_ATTEMPTS}" ]; then
        echo "aqt install failed after ${attempt} attempts" >&2
        exit 1
    fi
    echo "aqt install failed (attempt ${attempt}/${AQT_ATTEMPTS}), retrying in ${AQT_RETRY_DELAY}s..." >&2
    attempt=$((attempt + 1))
    sleep "${AQT_RETRY_DELAY}"
done
echo "Qt for Android installed under ${QT_PATH}/${QT_VERSION}/android"
