Usage: build-qgc-apk [QGC_ROOT] [options]

Build QGroundControl Android APKs with this repo's own Docker image.

Options:
    --root DIR            QGroundControl checkout (default: current git root)
    --abi ABI             x86_64, arm64-v8a, or all. Repeatable.
                          Default: arm64-v8a (full build, original
                          build_android output). Use all for both.
    --out DIR             Also copy the APK into this directory
    --name NAME           APK base name (default: QGroundControl)
    --jobs N              Parallel make jobs (default: 4)
    --image NAME          Docker image (default: qgc-android-builder:latest)
    --rebuild-image       Rebuild the Docker image first
    --clean               Remove each ABI's build directory first
    --x86-video           Try to build x86_64 with video streaming. This needs
                          GStreamer x86_64 libraries built with -fPIC; the
                          bundled official static libraries are not PIC.
    -h, --help            Show this message and exit

Build directories:
    arm64-v8a   <QGC_ROOT>/build_android
    x86_64      <QGC_ROOT>/build_android_x86_64

Output:
    arm64-v8a:
        build_android/android-build/build/outputs/apk/release/android-build-release-signed.apk
    x86_64:
        build_android_x86_64/android-build/build/outputs/apk/release/android-build-release-signed.apk

With --out DIR the APK is also copied as <name>-<abi>[-novideo].apk.

Exit codes:
    0  all requested ABIs built
    1  build failed (Docker, qmake, make, signing, or copy)
    2  bad usage
