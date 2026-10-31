#!/usr/bin/env bash

set -e

#=============================================================================
# install-qgc-apk-via-usb.sh
#
# Install QGroundControl APK to a USB-connected Android device.
#
# Usage:
#   install-qgc-apk-via-usb.sh [apk_path]
#
# If no apk_path is provided, it will look for QGroundControl64.apk
# in build_android/package/ relative to the QGC repository root.
# The script determines the QGC repo root using git from the current working directory.
#=============================================================================

PACKAGE="Aiseed.GCS.RD"

echo "=========================================="
echo " Android APK USB Installer (QGC)"
echo "=========================================="

# Check adb is available
if ! command -v adb &> /dev/null; then
    echo "Error: adb not found. Install Android SDK platform-tools first."
    exit 1
fi

# Determine APK path
APK_PATH=""

if [ -n "${1:-}" ]; then
    APK_PATH="$1"
fi

if [ -z "$APK_PATH" ]; then
    # Try to find QGC repo root from current working directory
    if command -v git &> /dev/null; then
        QGC_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ -n "$QGC_ROOT" ]; then
            CANDIDATE="$QGC_ROOT/build_android/package/QGroundControl64.apk"
            if [ -f "$CANDIDATE" ]; then
                APK_PATH="$CANDIDATE"
            else
                # Fallback: search for any QGroundControl*.apk under build_android/package
                APK_PATH="$(find "$QGC_ROOT/build_android" -name "QGroundControl*.apk" 2>/dev/null | head -n 1 || true)"
            fi
        fi
    fi
fi

if [ -z "$APK_PATH" ]; then
    # Fallback: look in current working directory
    if [ -f "./build_android/package/QGroundControl64.apk" ]; then
        APK_PATH="./build_android/package/QGroundControl64.apk"
    elif [ -f "QGroundControl64.apk" ]; then
        APK_PATH="QGroundControl64.apk"
    else
        APK_PATH="$(find . -name "QGroundControl*.apk" 2>/dev/null | head -n 1 || true)"
    fi
fi

# Check APK exists
if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
    echo "Error: APK not found."
    echo "Searched relative to current directory ($PWD) and git repo root."
    echo "Expected: build_android/package/QGroundControl64.apk (in QGC repo)"
    echo "Usage: install-qgc-apk-via-usb.sh [apk_path]"
    exit 1
fi

# Check device connected
echo "Checking for connected device..."
DEVICES=$(adb devices | grep -v "List of devices" | grep -v "^$" | grep "device$" | wc -l)

if [ "$DEVICES" -eq 0 ]; then
    echo "Error: No authorized device connected."
    echo "1. Connect Android device via USB"
    echo "2. Enable Developer Options > USB Debugging"
    echo "3. Allow USB debugging prompt on device"
    exit 1
fi

echo "Device found:"
adb devices | grep "device$"

# Install APK
echo "Installing APK: $APK_PATH"
adb install -r "$APK_PATH"

echo ""
echo "=========================================="
echo " Installation complete!"
echo "=========================================="
