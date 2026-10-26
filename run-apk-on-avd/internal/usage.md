Usage:
    run-apk-on-avd.cmd APK_PATH [APK_PATH ...]

Run one or more APKs on the 1440x3120 Android virtual device (S24 Plus).
Drag an APK onto this file to launch it; the emulator opens a visible
window and keeps running so the app can be seen and used.

Options (pass them after the APK):
    --avd NAME        AVD name to create or reuse (default: s24-plus)
    --resolution WxH  Display resolution (default: 1440x3120)
    --emulator PATH   Path to the emulator binary
    --sdk-root DIR    Android SDK root directory
    --api LEVEL       Android API level (default: 35)
    --image-tag TAG   System image tag (default: google_apis)
    --abi ABI         System image ABI (default: x86_64)
                      arm64-v8a is only usable on an arm64 host; recent
                      emulators reject arm64 guests on x86_64 hosts
    --port PORT       Emulator console port (default: 5554)
    --no-boot-wait    Do not wait for the boot animation to finish
    --headless        Hide the emulator window (default: visible window)
    --scale FACTOR      Emulator window scale (for example 0.5)
    --window-size WxH   Resize the emulator window after launch
    --window-position X,Y  Move the emulator window after launch
    --gpu MODE        GPU mode: auto, host, software, swangle,
                      swiftshader, lavapipe (default: swangle)
    --software-emulation
                      Permit very slow software emulation without KVM
    --timeout SECONDS Boot timeout (default: 600)

Exit codes:
    0  APK installed and emulator running
    1  APK missing, SDK/AVD provisioning, emulator, install, or boot failed
    2  no APK argument given
