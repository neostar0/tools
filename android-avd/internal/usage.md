Usage: android-avd.sh <command> [options]

Open, close and position Android Virtual Devices.

Commands:
    open       Start (or reuse) the emulator window and wait for boot.
    close      Stop a running emulator.
    geometry   Move and/or resize a running emulator window.
    list       List configured AVDs and their ABI.
    status     List running emulators, adb state and AVD name.

open options:
    --avd NAME            AVD name (default: s24-plus for x86_64,
                          s24-plus-<abi> otherwise)
    --abi ABI             System-image ABI (default: x86_64)
    --api LEVEL           Android API level (default: 35)
    --image-tag TAG       System-image tag (default: google_apis)
    --resolution WxH      Guest display resolution (default: 1440x3120)
    --port PORT           Emulator console port (default: 5554)
    --gpu MODE            auto, host, software, swangle, swiftshader, lavapipe
                          (default: swangle)
    --emulator PATH       Use this emulator binary
    --headless            Run without a visible window
    --software-emulation  Allow slow software CPU emulation
    --timeout SECONDS     Boot timeout (default: 600)
    --no-boot-wait        Return as soon as adb connects
    --scale FACTOR        Emulator window scale (for example 0.5)
    --window-size WxH     Resize the host window (needs wmctrl on Linux)
    --window-position X,Y Move the host window
    --no-activate         Do not raise the window
    --sdk-root DIR        Android SDK root directory

close options:
    --avd NAME | --port PORT | --serial SERIAL | --all

geometry options:
    --avd NAME            AVD of the running emulator (optional if running)
    --port PORT           Emulator console port (default: 5554)
    --window-size WxH     New host window size
    --window-position X,Y New host window position
    --no-activate         Do not raise the window

Exit codes:
    0  success
    1  SDK/AVD/emulator/window operation failed
    2  bad usage
