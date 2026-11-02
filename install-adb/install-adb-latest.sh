#!/bin/bash

TARGET_DIR="/opt/android-sdk"
BACKUP_DIR=""

# Detect OS and CPU architecture.
# Google publishes official platform-tools for:
#   - Linux: x86_64 only (the Linux build is an x86-64 ELF binary)
#   - macOS: universal binary (Intel + Apple Silicon)
#   - Windows: x86_64
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux)
        case "$ARCH" in
            x86_64|amd64)
                ZIP_NAME="platform-tools-latest-linux.zip"
                ;;
            *)
                # This script only installs the latest official Google platform-tools.
                # Google does not publish them for Linux ARM or 32-bit x86.
                echo "Error: unsupported architecture 'Linux/$ARCH'."
                echo "Google only provides the latest Linux platform-tools for x86_64."
                echo "This script installs the latest version, so it will not fall back"
                echo "to an older distribution package. Install 'adb'/'fastboot' manually"
                echo "from your distribution if you still want them."
                exit 1
                ;;
        esac
        ;;
    Darwin)
        ZIP_NAME="platform-tools-latest-darwin.zip"
        # /opt is not writable by default on macOS.
        TARGET_DIR="/usr/local/share/android-sdk"
        ;;
    *)
        echo "Error: unsupported OS '$OS'."
        echo "On Windows, download platform-tools-latest-windows.zip from:"
        echo "  https://developer.android.com/tools/releases/platform-tools"
        exit 1
        ;;
esac

# 0. Print current adb version if it exists
if command -v adb &> /dev/null && adb version &> /dev/null; then
    echo "Current ADB version detected:"
    adb version
    echo "-----------------------------------"
else
    echo "Notice: 'adb' is not currently installed or not in PATH."
    echo "-----------------------------------"
fi

# 1. Check if the target directory already exists
if [ -d "$TARGET_DIR" ]; then
    echo "Notice: Detected that $TARGET_DIR already exists."
    read -p "Do you want to proceed with the installation and overwrite it? (y/N): " choice

    # Exit if the user does not input 'y' or 'Y'
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
        echo "Installation cancelled by the user."
        exit 0
    fi

    # 2. Rename the old directory as a backup before proceeding
    BACKUP_DIR="${TARGET_DIR}_bak_$(date +%Y%m%d_%H%M%S)"
    echo "Backing up the old directory to: $BACKUP_DIR"
    sudo mv "$TARGET_DIR" "$BACKUP_DIR"
fi

# 3. Perform the installation
if [ "$OS" = "Linux" ]; then
    echo "Purging old apt packages..."
    sudo apt-get purge -y android-tools-adb adb || true

    echo "Installing dependencies..."
    sudo apt-get update
    sudo apt-get install -y curl unzip android-sdk-platform-tools-common
else
    for dep in curl unzip; do
        if ! command -v "$dep" &> /dev/null; then
            echo "Error: '$dep' is required (e.g. brew install $dep)." >&2
            exit 1
        fi
    done
fi

echo "Downloading latest Google Android Platform Tools ($OS/$ARCH)..."
WORK_DIR="$(mktemp -d)"
cd "$WORK_DIR" || exit 1
curl -fLO "https://dl.google.com/android/repository/$ZIP_NAME"

echo "Extracting files to $TARGET_DIR..."
unzip -o "$ZIP_NAME"
sudo rm -rf "$TARGET_DIR"
sudo mkdir -p "$TARGET_DIR"
# Keep the platform-tools directory so adb lives at $TARGET_DIR/platform-tools/adb
sudo mv "$WORK_DIR/platform-tools" "$TARGET_DIR/platform-tools"

# Set permissions
sudo chown -R 0:0 "$TARGET_DIR"
sudo chmod -R a+rX "$TARGET_DIR"

# Create system-wide symlinks
sudo mkdir -p /usr/local/bin
sudo ln -sfn "$TARGET_DIR/platform-tools/adb" /usr/local/bin/adb
sudo ln -sfn "$TARGET_DIR/platform-tools/fastboot" /usr/local/bin/fastboot

# Verify installation
echo "Verifying new installation..."
"$TARGET_DIR/platform-tools/adb" version
ADB_STATUS=$?
"$TARGET_DIR/platform-tools/fastboot" --version
FASTBOOT_STATUS=$?

# Cleanup temporary download
rm -rf "$WORK_DIR"

# Check if installation was successful
if [ $ADB_STATUS -eq 0 ] && [ $FASTBOOT_STATUS -eq 0 ]; then
    echo "Installation completed successfully."

    # 4. Remove the old backup directory after a successful installation
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        echo "Cleaning up the old backup directory..."
        sudo rm -rf "$BACKUP_DIR"
        echo "Cleanup completed!"
    fi
else
    echo "Error: Installation failed!"
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        echo "Restoring the previous version from backup..."
        sudo rm -rf "$TARGET_DIR"
        sudo mv "$BACKUP_DIR" "$TARGET_DIR"
        echo "Restoration complete."
    fi
    exit 1
fi
