# First deliverable: overlay feasibility APK

Physical BRAVIA 9 + PS5 HDMI result: **NOT TESTED**.

Build from repository root with JDK 17+ and Android SDK 35:
```sh
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export ANDROID_HOME="$HOME/Library/Android/sdk"
./gradlew :tv-overlay:assembleDebug
export PATH="$ANDROID_HOME/platform-tools:$PATH"
```
APK: `apps/tv-overlay/build/outputs/apk/debug/tv-overlay-debug.apk`.

On TV: Settings → System → About → select Android TV OS build seven times.
In Developer options enable debugging; exact Sony labels vary. Use Wireless debugging
pairing if offered (`adb pair TV_IP:PAIR_PORT`, then `adb connect TV_IP:DEBUG_PORT`).
On older TVs offering network ADB, use `adb connect TV_IP:5555` and approve the TV prompt.
USB ADB is an alternative only if the TV exposes a supported debugging port; do not assume
ordinary USB media ports provide ADB. Never expose ADB through a router port forward.

```sh
adb devices
adb install -r apps/tv-overlay/build/outputs/apk/debug/tv-overlay-debug.apk
adb shell am start -n dev.ps5thaisub.overlay/.MainActivity
```
Open **Request Overlay Permission**, allow draw over other apps, return to app.
If Sony omits that settings screen, the optional ordinary app permission workaround is:
```sh
adb shell appops set dev.ps5thaisub.overlay SYSTEM_ALERT_WINDOW allow
```
Press **Show Thai Test Subtitle**. It starts the foreground service and displays
`เราต้องออกจากที่นี่ก่อนรุ่งสาง` for 30 seconds. Press **Hide Subtitle** to remove it.
Text size, opacity and bottom safe area controls cycle through presets. Use the TV remote
for app controls; keep DualSense paired directly to PS5. Switch to the PS5 HDMI input
within 30 seconds and record visibility. Repeat as needed, then Stop Service.

Use `docs/MANUAL_ACCEPTANCE.md` for the gate. If HDMI fails, stop TV-dependent rollout;
use the Mac viewer. An emulator pass is not an HDMI pass.

Restore: Stop Service; revoke draw-over permission in Settings (or
`adb shell appops set dev.ps5thaisub.overlay SYSTEM_ALERT_WINDOW default`), revoke debugging
authorizations and disable wireless/USB debugging. Optionally uninstall with
`adb uninstall dev.ps5thaisub.overlay`. No launcher, battery or HDMI settings are changed.
