# install-qgc-apk-via-usb

Install the APK that `build_android` produced on a USB-attached device
without typing the build path: the script finds the APK itself.

## Command Line

```bash
./install-qgc-apk-via-usb.sh [apk-path]
```

With no argument it searches, in order: `build_android/package/QGroundControl64.apk`
under the current git repository root, any `QGroundControl*.apk` below that
`build_android` folder, `./build_android/package/QGroundControl64.apk`, and
finally any `QGroundControl*.apk` below the working directory. The first match
is installed with `adb install -r`, which keeps the app's data on upgrades.

## Exit codes

`0` — the APK was installed; `1` — `adb` is not installed, no authorized device
is connected, no APK was found, or `adb install` failed.

## Requirements

Linux/macOS with Bash and `adb` from the Android SDK platform-tools; the device
must be unlocked with USB debugging enabled and authorised.
