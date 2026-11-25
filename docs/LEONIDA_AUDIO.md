# Leonida actual audio → Android TV (experimental)

## What changed

Mac 0.6.0 adds `leonida-tv-bridge --audio`. It captures **only th.leonidasub.app**
through the existing native ScreenCaptureKit helper and forwards the actual waveform,
not a new synthesis of the caption text. No microphone, all-system fallback, translation
library extraction, saved audio or transcript. Other Leonida app sounds may be included.

Android APK 0.2.0/versionCode 2 adds authenticated `/v1/audio` and bounded AudioTrack
playback. Audio starts OFF at each service start. **Enable Thai Audio**, **Mute Thai Audio**,
and Stop Service give explicit control. Muting stops playback and rejects further audio.
The service declares mediaPlayback alongside its overlay foreground-service type.

## Install and run at home

1. Install `artifacts/tv-overlay-audio-debug.apk` over the existing app (same signing key).
   Start Service, then **Enable Thai Audio**. Existing pairing settings should remain.
2. Enable Leonida **อ่านออกเสียง** on Mac. In its voice settings, use **ทดลองฟัง**.
3. Verify capture before connecting the TV:

```sh
uv run --project apps/mac-translator leonida-audio-check --seconds 15
```

Press Leonida's sample button during the check. Nonzero peak proves a signal, not intelligibility.
If audible Mac speech yields zero capture, macOS may attribute system-synthesized voice to
another process. This version intentionally does not expand to all-system audio; such a
configuration needs further investigation before claiming actual Leonida voice forwarding.

4. Stop any prior bridge/translator, export `PS5_TV_TOKEN`, then run:

```sh
uv run --project apps/mac-translator leonida-tv-bridge \
  --source MAC_LAN_IP --target TV_IP --audio
```

Mac source is the reachable interface for Leonida's viewer (not necessarily the VPN address
shown by its QR). App and TV must be reachable. Do not expose these LAN services publicly.
Omit `--audio` for captions only. A previous APK returns 404 and the audio bridge stops with
an upgrade/pairing message. A muted TV returns 409; PCM is dropped while retrying session start.

## Protocol and latency bounds

`POST /v1/audio`, same bearer token/LAN/origin validation as captions, body <=8192 bytes:

```json
{"action":"chunk","session":"random-session-id","sequence":1,"sample_rate":16000,"channels":1,"format":"s16le","pcm":"BASE64_3200_BYTES"}
```

Start/stop use the same fields without pcm. Sequence starts at 0 for start and increases.
100ms PCM16 mono packets: raw 32 KB/s, around 43 KB/s after base64 plus HTTP overhead.
The sender retains at most two chunks, discards items older than 250ms, never retries PCM,
and starts a new session after transport failure. A separate sender thread keeps caption
handling independent. No VAD clips Thai speech. Session expiry is 750ms, checked every
250ms, so disconnect silence is enforced in roughly 0.75–1s plus hardware output buffering.
Android writes nonblocking into a bounded stream buffer, flushes on sequence gaps/overflow,
and releases the track on mute, stop, service teardown or expiry. Duplicate/out-of-order
sequence numbers in an active session are rejected. Intended for one sender per TV.

This does **not** eliminate Leonida's own queued read-aloud delay or suppress Mac playback.
Do not mute Leonida's own speech volume to avoid echo: that may also silence captured audio.
Measured end-to-end latency is not available yet; 100ms is packet duration, not total latency.
Default track volume is 70% of the TV's media volume. No audio focus is requested to avoid
interrupting the HDMI source. Whether app audio can mix while viewing HDMI, including
ARC/eARC/Bluetooth outputs, depends on the TV and must be tested.

## Verification and outstanding hardware checks

- Python: 66 tests pass; includes exact PCM reconstruction, no VAD truncation, bounded queue,
  packet format, no retry of failed chunks and source-close handling.
- Android: 7 JVM tests pass; includes auth/body bounds, invalid PCM rejection, active-session
  replay protection, explicit stop and monotonic expiry. APK build and lint pass.
- Native source capture starts for Leonida; initial no-speech check returned silence. The
  attempted sample click did not execute because the app moved to another Space. Actual
  synthesized speech capture is **not yet verified**.
- User is outside home. New APK installation, audible TV playback, HDMI coexistence, hardware
  mute/stop/watchdog, intelligibility, jitter and actual delay still require hardware checks.

AudioTrack implementation checked against Android's official reference:
https://developer.android.com/reference/android/media/AudioTrack
