Usage: run-qgc-apk.sh [QGC_ROOT] [--run-apk-on-avd options]

Run the QGroundControl APK on the 1440x3120 Android virtual device (S24 Plus).

The APK path is derived from the QGC repository. With --abi it prefers the
build output, then the dist copy:
    arm64-v8a: <QGC_ROOT>/build_android/android-build/.../android-build-release-signed.apk
    x86_64:    <QGC_ROOT>/build_android_x86_64/android-build/.../android-build-release-signed.apk
    then:      <QGC_ROOT>/dist/QGroundControl-<abi>[-novideo].apk
Without --abi the arm64 build_android output is preferred, then x86_64:
    <QGC_ROOT>/build_android/android-build/build/outputs/apk/release/android-build-release-signed.apk
    <QGC_ROOT>/dist/QGroundControl-arm64-v8a.apk
    <QGC_ROOT>/build_android_x86_64/android-build/.../android-build-release-signed.apk
    <QGC_ROOT>/dist/QGroundControl-x86_64*.apk
Fallbacks:
    <QGC_ROOT>/dist/*.apk
    <QGC_ROOT>/build_android/package/QGroundControl64.apk

Arguments:
  QGC_ROOT          Path to the QGroundControl git repository.
                    Default: current git repo root, or the sibling "qgc"
                    directory next to this tools repo.
  --avd NAME        AVD name to create or reuse (default: s24-plus)
  --resolution WxH  Display resolution (default: 1440x3120)
  --timeout SECONDS Boot timeout (default: 600)
  --no-boot-wait    Do not wait for the boot animation to finish
  --headless        Hide the emulator window (default: visible window)
  --window-size WxH   Resize the emulator window after launch
  --window-position X,Y  Move the emulator window after launch
  --gpu MODE        GPU mode: auto, host, software, swangle,
                    swiftshader, lavapipe (default: swangle)
  --sdk-root DIR    Android SDK root directory
  --api LEVEL       Android API level (default: 35)
  --image-tag TAG   System image tag (default: google_apis)
  --abi ABI         Select the APK and the emulator ABI. Repeatable values
                    used by qgc-android-builder: x86_64 or arm64-v8a.
                    On an x86_64 host only x86_64 AVDs can run; arm64 APKs
                    need a physical device.
  --apk PATH        Use this APK instead of searching the QGC repo
  --software-emulation
                    Permit very slow software emulation without KVM
  -h, --help        Show this message and exit

Exit codes: 0 = APK launched, 1 = QGC root or APK not found, or launch failed,
2 = bad usage.
