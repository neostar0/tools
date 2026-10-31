# deploy-qgc-apk

QGroundControl-specific Android helpers: build the "AiseedGCS RD" APK variant
(RD watermark, its own app name and package id) and push the result onto a
tablet over USB.

## Command Line

```bash
./build-android-rd.sh                            # build the RD variant
./install-android-usb.sh [apk-path]              # install it with adb
python3 androidMfileProcess.py <makefile> <out>  # rewrite a generated Makefile
```

`build-android-rd.sh` backs up `android/AndroidManifest.xml`,
`qgroundcontrol.pro`, `aiseedResourse/ExeHandler.h` and
`QGCPostLinkInstaller.pri`, rewrites the app name and package to
`AiseedGCS RD` / `Aiseed.GCS.RD`, adds the RD watermark through
`android/add_rd_watermark.py`, then runs `./build-android.sh`. The backups are
restored on exit whatever the outcome, so a failed build leaves the tree clean.

`install-android-usb.sh` installs `build_android/package/QGroundControl64.apk`
with `adb install`, or the path given as its argument. The argument can also
come from a caller that already knows the APK location.

`androidMfileProcess.py` strips the `@echo moc ... &&` fragments from every
line of a Qt-generated Makefile and replaces the input file with the rewritten
copy. Both arguments are required; without them it falls back to the
development-time path it was written against and fails to open it.

Both shell scripts `cd` to their own folder first, so they are meant to be run
from - or copied into - the root of a QGC Android checkout: the build script
calls the `build-android.sh` next to it and the installer defaults to
`build_android/package/` relative to itself.

## Exit codes

`0` — the build, the install or the Makefile rewrite finished; `1` — the APK is
missing, `adb` is not installed, no authorized device is connected,
`adb install` failed, or the build failed. A failure inside the build script
propagates its own non-zero status.

## Requirements

Linux/macOS with Bash, `adb` from the Android SDK platform-tools for the
installer, and Qt's Android toolchain plus `python3` (with Pillow, used by
`add_rd_watermark.py`) for the builder.
