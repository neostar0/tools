# QGroundControl Android Builder

Build QGroundControl APKs for both Android ABIs from this tools repo, using its
own Dockerfile (no dependency on the QGC checkout's Docker scripts). The
`x86_64` build runs natively on x86_64 emulators; the `arm64-v8a` build is the
full device build with video streaming.

## Command Line

```bash
build-qgc-apk --abi all
build-qgc-apk --root ~/qgc --abi x86_64
build-qgc-apk --abi arm64-v8a --jobs 8
```

## Options

| Flag              | Default                      | Description                                 |
| ----------------- | ---------------------------- | ------------------------------------------- |
| `--root`          | current git root             | QGroundControl checkout                     |
| `--abi`           | `arm64-v8a`                  | `x86_64`, `arm64-v8a`, or `all`; repeatable |
| `--out`           | none                         | Also copy the APK into this directory       |
| `--name`          | `QGroundControl`             | APK base name                               |
| `--jobs`          | `4`                          | Parallel make jobs                          |
| `--image`         | `qgc-android-builder:latest` | Docker image                                |
| `--rebuild-image` | off                          | Rebuild the Docker image                    |
| `--clean`         | off                          | Remove each ABI's build directory           |
| `--x86-video`     | off                          | Try x86_64 with video (needs PIC GStreamer) |

## Output

The canonical APK paths are the build directories:
- arm64-v8a — full build with video streaming.
- x86_64 — native UI build. Video streaming is disabled because the official
  GStreamer x86_64 static libraries are not position-independent and Android
  rejects the resulting text relocations.

Build directories:
- arm64-v8a: `<root>/build_android/android-build/build/outputs/apk/release/android-build-release-signed.apk`
- x86_64: `<root>/build_android_x86_64/android-build/build/outputs/apk/release/android-build-release-signed.apk`

`--out DIR` optionally copies the APK as `<name>-<abi>[-novideo].apk`.

The tool signs with the checkout's `android/android_release.keystore`. It reads
`ANDROID_KEYSTORE_PASSWORD` from the environment, then from the checkout's
`build-android.sh`; without either it produces an unsigned APK.

## Exit codes

`0` — all requested ABIs built, `1` — build failed, `2` — bad usage.

## Requirements

Docker. The first build creates the `qgc-android-builder` image (Qt 5.15.2 for
Android, GStreamer 1.18.6, Android SDK/NDK) and can take a while; later builds
reuse it. Builds run in a container and write only under the checkout's
`build_android_<abi>` directory and the output directory.
