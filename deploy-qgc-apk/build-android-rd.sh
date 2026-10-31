#! /usr/bin/env bash

set -e

#=============================================================================
# build-android-rd.sh
#
# Builds the "AiseedGCS RD" Android APK variant with RD watermark on icons.
#
# Usage:
#   ./build-android-rd.sh
#
# Output APK: build_android/
#=============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="AiseedGCS RD"
PACKAGE_NAME="Aiseed.GCS.RD"

echo "=========================================="
echo " Android RD Variant Builder"
echo " App name: $APP_NAME"
echo " Package: $PACKAGE_NAME"
echo "=========================================="

# Files that need app name substitution
MANIFEST_FILE="android/AndroidManifest.xml"
PRO_FILE="qgroundcontrol.pro"
EXEHANDLER_FILE="aiseedResourse/ExeHandler.h"
INSTALLER_FILE="QGCPostLinkInstaller.pri"

# Backup original files
backup_files() {
    for file in "$MANIFEST_FILE" "$PRO_FILE" "$EXEHANDLER_FILE" "$INSTALLER_FILE"; do
        if [ -f "$file" ] && [ ! -f "${file}.bak" ]; then
            cp "$file" "${file}.bak"
        fi
    done
}

# Restore original files
restore_files() {
    for file in "$MANIFEST_FILE" "$PRO_FILE" "$EXEHANDLER_FILE" "$INSTALLER_FILE"; do
        if [ -f "${file}.bak" ]; then
            cp "${file}.bak" "$file"
            rm "${file}.bak"
        fi
    done
}

# Apply app name to all config files
apply_app_name() {
    local app_name="$1"
    local package_name="$2"
    echo "  Setting app name to: $app_name"
    echo "  Setting package to: $package_name"

    sed -i "s/QGC_APP_NAME        = \".*\"/QGC_APP_NAME        = \"$app_name\"/" "$PRO_FILE"
    sed -i "s/android:label=\"[^\"]*\"/android:label=\"$app_name\"/g" "$MANIFEST_FILE"
    sed -i "s/AISEED_APP_NAME = QString::fromUtf8(\".*\")/AISEED_APP_NAME = QString::fromUtf8(\"$app_name\")/" "$EXEHANDLER_FILE"
    sed -i "s/--sign \${SOURCE_DIR}\/android\/android_release\.keystore .*/--sign \${SOURCE_DIR}\/android\/android_release.keystore $app_name --storepass \$\$(ANDROID_KEYSTORE_PASSWORD)/" "$INSTALLER_FILE"
    sed -i "s/package=\"[^\"]*\"/package=\"$package_name\"/" "$MANIFEST_FILE"
}

# Add RD watermark to Android icons
add_watermark() {
    echo "  Adding RD watermark to icons..."
    python3 android/add_rd_watermark.py android/res/
}

# Main execution
main() {
    echo "Backing up original files..."
    backup_files

    # Ensure cleanup on exit
    trap restore_files EXIT

    apply_app_name "$APP_NAME" "$PACKAGE_NAME"
    add_watermark

    echo ""
    echo "------------------------------------------"
    echo " Building: $APP_NAME"
    echo "------------------------------------------"

    # Call build-android.sh for the actual build
    ./build-android.sh

    echo ""
    echo "=========================================="
    echo " RD variant built successfully!"
    echo "=========================================="
    echo ""
    echo "Output: build_android/"
    echo ""
}

main "$@"
