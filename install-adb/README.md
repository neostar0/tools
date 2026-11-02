# install-adb

Replace whatever `adb` and `fastboot` a machine has with the latest official
Google Android platform-tools, downloaded straight from Google.

Linux x86_64 and macOS (Intel and Apple Silicon) only. Google does not
publish Linux ARM builds, so the script refuses unsupported platforms
instead of silently falling back to an older distribution package.

## Command Line

Linux/macOS only. Run from anywhere.

```bash
./install-adb-latest.sh
```

On Linux the script first purges the old `android-tools-adb`/`adb` APT
packages and installs `curl`, `unzip` and `android-sdk-platform-tools-common`.
On macOS `curl` and `unzip` must already be present (for example via Homebrew).

The archive is unpacked into `/opt/android-sdk` (`/usr/local/share/android-sdk`
on macOS) and `adb`/`fastboot` are linked into `/usr/local/bin`.

If the target directory already exists the script asks before overwriting,
renames the old copy to a timestamped backup, and removes that backup only
after the new `adb` and `fastboot` verify successfully. A failed verification
restores the backup. Declining the prompt changes nothing.

## Exit codes

`0` — installation succeeded, or you declined the overwrite prompt;
`1` — unsupported OS/architecture, a missing dependency, or a failed
download/verification.

## Requirements

`sudo`, `curl` and `unzip`. The script downloads from
`https://dl.google.com/android/repository/`, so it needs network access.
