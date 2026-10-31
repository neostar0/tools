#! /usr/bin/env bash

set -e

#=============================================================================
# install-android-usb.sh
#
# Install QGroundControl APK to a USB-connected Android device.
#
# Usage:
#   ./install-android-usb.sh [apk_path]
#
# Default APK: build_android/package/QGroundControl64.apk
#=============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APK_PATH="${1:-build_android/package/QGroundControl64.apk}"
PACKAGE="Aiseed.GCS.RD"

echo "=========================================="
echo " Android APK USB Installer"
echo "=========================================="

# Check APK exists
if [ ! -f "$APK_PATH" ]; then
    echo "Error: APK not found: $APK_PATH"
    exit 1
fi

# Check adb is available
if ! command -v adb &> /dev/null; then
    echo "Error: adb not found. Install Android SDK platform-tools first."
    exit 1
fi

# Check device connected
echo "Checking for connected device..."
DEVICES=$(adb devices | grep -v "List of devices" | grep -v "^$" | grep "device$" | wc -l)

if [ "$DEVICES" -eq 0 ]; then
    echo "Error: No authorized device connected."
    echo "1. Connect Samsung tablet via USB"
    echo "2. Enable Developer Options > USB Debugging"
    echo "3. Allow USB debugging prompt on tablet"
    exit 1
fi

echo "Device found:"
adb devices | grep "device$"

# Install APK
echo "Installing APK: $APK_PATH"
adb install "$APK_PATH"

echo ""
echo "=========================================="
echo " Installation complete!"
echo "=========================================="
