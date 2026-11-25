# PS5 → Mac → Thai subtitles

Working proof of concept: an Android TV overlay APK, authenticated Mac caption bridge,
local speech/translation adapters and a Mac browser fallback. **BRAVIA 9 HDMI: NOT TESTED.**
Keep PS5 on ordinary HDMI and DualSense paired directly to PS5. No capture card, Remote
Play, Android phone, launcher replacement or paid service is required.

Start with [M0 APK installation and physical gate](docs/M0_INSTALL.md). The first test
is **Show Thai Test Subtitle → switch to PS5 HDMI**. If Sony blocks the overlay, record
FAIL and use the Mac viewer. Do not continue TV-dependent deployment on a failed gate.

## Build and install the APK

Requires JDK 17+ and Android SDK 35 (Android Studio can supply both).
```sh
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
./gradlew assembleDebug lintDebug testDebugUnitTest
adb install -r apps/tv-overlay/build/outputs/apk/debug/tv-overlay-debug.apk
adb shell am start -n dev.ps5thaisub.overlay/.MainActivity
```
Enable TV debugging and connect/pair first: exact options and cleanup are in the
[M0 guide](docs/M0_INSTALL.md). Open Request Overlay Permission; grant draw-over permission;
press Show Thai Test Subtitle. Hide Subtitle and Stop Service are explicit controls.
The local test lasts 30 seconds; network captions last 250ms–15s.

## Mac setup and demo (no AI download)

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. Commands below run from
`apps/mac-translator`:
```sh
cd apps/mac-translator
uv sync --locked
uv run ps5-thai-sub run --demo
# Open http://127.0.0.1:8766 in a browser. Ctrl-C stops.
uv run ps5-thai-sub run --demo --demo-once
```
The three fixture translations are deterministic test data, not model-quality evidence.
The viewer uses large Thai text and automatically hides expired captions. It is included
in the Python package, so installation does not depend on repository-relative assets.

## Pair Mac to TV

Start Service on TV; read the TV IP and random pairing token from its screen. Mac IP
entry is unnecessary because the Mac initiates HTTP requests. Keep both on a trusted
private LAN. Set `TV_IP` to the displayed address and enter the token without shell history:
```sh
export TV_IP=192.168.1.50  # replace with your TV address
read -s PS5_TV_TOKEN
export PS5_TV_TOKEN
uv run send-test-caption --tv-host "$TV_IP" --token "$PS5_TV_TOKEN" --text "เราต้องออกจากที่นี่ก่อนรุ่งสาง"
uv run ps5-thai-sub run --demo --target "$TV_IP" --token "$PS5_TV_TOKEN"
# Empty text hides immediately:
uv run send-test-caption --tv-host "$TV_IP" --text ""
```
Token environment variable is preferable to `--token`, which can appear in process lists.
Examples show both because the CLI supports the requested flag. The TV displays the token
only in its launcher screen; do not share screenshots of that screen without redaction.

TCP 8765 must reach the TV from Mac. Guest Wi-Fi/client isolation may block it; no router
port forward is needed. The listener rejects public-source addresses and requires auth
on health as well as captions. HTTP is not encrypted: use only a trusted isolated LAN.
Mac browser viewer binds loopback only. See [protocol and security limits](packages/protocol/README.md).

## Remote Play audio (new)

Capture audio directly from PS Remote Play instead of the room microphone:
```sh
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-audio --target "$TV_IP" --model openthai
```
Keep app audio enabled, Whisper and Ollama running. No loopback driver is needed.
[Setup, permissions and audio-level checks](docs/REMOTE_PLAY_AUDIO.md). This is a separate
input mode from OCR; it still hears game music/effects mixed by Remote Play.

## Remote Play OCR (new)

To read English subtitles directly from PS Remote Play instead of the microphone, use
`--input remote-play-ocr`. [Setup and region calibration](docs/REMOTE_PLAY_OCR.md).
This optional mode uses Apple ScreenCaptureKit + Vision, then the same Thai translator
and TV bridge. It needs Screen Recording permission, not Whisper. It is implemented and
synthetic-window tested; actual Remote Play game-session validation is pending.

## Choose the translation model

OpenThai is the user-selected default. No APK update is required. From repository root:
```sh
uv run --project apps/mac-translator ps5-thai-sub models
# Use OpenThai (also selected when --model is omitted):
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-ocr --target "$TV_IP" --model openthai
# Switch to Gemma by stopping the running CLI and starting again:
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-ocr --target "$TV_IP" --model gemma
```
Microphone, Remote Play audio and OCR modes support the same choice. Full provider model IDs still
work. Priority: explicit `--model` → `TRANSLATION_MODEL` environment → OpenThai default.
An old exported `TRANSLATION_MODEL=gemma3:4b` overrides the default; unset it or use
`--model openthai`. Startup logs identify the selected model. Switching is on restart,
not a live browser control. Demo mode continues to use fixtures, not AI.

This default is a preference, not a claim that OpenThai is more accurate. Both models
made meaningful translation mistakes in the [comparison](docs/TRANSLATION_COMPARISON.md).

## Local AI on Apple Silicon

Use a warm whisper.cpp server for English ASR, plus Ollama for Thai translation.
These are external dependencies; no upstream source is modified or copied into this repo.
Tested runtime versions and model observations are in [TEST_REPORT.md](TEST_REPORT.md).
From repository root, install the ASR runtime and download an English model:
```sh
brew install whisper-cpp
mkdir -p artifacts/models
curl -L --fail https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin -o artifacts/models/ggml-base.en.bin
whisper-server -m artifacts/models/ggml-base.en.bin --host 127.0.0.1 --port 18080 -l en
```
Keep that terminal open. In another terminal with Ollama installed/running:
```sh
ollama pull openthai/openthai-1.5-7b
# If Ollama is not already running: ollama serve
cd apps/mac-translator
uv run ps5-thai-sub devices
uv run ps5-thai-sub run --input microphone --target "$TV_IP" --token "$PS5_TV_TOKEN" --transcriber whisper-server --translator openai-compatible --whisper-url http://127.0.0.1:18080 --model openthai
```
Omit `--target` for Mac-only fallback. Choose `--device N` from the device list if needed.
macOS may ask to allow microphone access for the terminal/app that launched Python;
check System Settings → Privacy & Security → Microphone. Put Mac near TV speakers,
reduce room noise, and use `--vad-threshold 0.02` if game music triggers excess chunks.
Energy VAD is not a dialogue-isolation model and may miss quiet lines.

Intel Macs can use whisper.cpp CPU (`--no-gpu` on the server); inference may be slower.
Metal/Core ML availability depends on hardware/build; this client makes no Apple
Translation language-pair assumption. PortAudio via sounddevice must support 16kHz mono
on the selected device. This proof of concept does not resample incompatible devices.

To use a different compatible translation provider, export the variables from
[.env.example](apps/mac-translator/.env.example), or pass `--translation-url` and `--model`.
`.env` files are **not** automatically loaded. Use an HTTPS endpoint for cloud services;
that sends transcripts/context to that provider and may incur its charges. No cloud
credentials are bundled. Default configuration stays on localhost.

Only final utterances are published. A three-phrase context window and bounded cache are
in memory. Prompts request proper-name preservation and no additions; AI can still
mishear or mistranslate. No algorithm guarantees hallucination-free output. Have a fluent
Thai reader evaluate the chosen model on real game dialogue. Client logs omit live audio,
transcripts and tokens. Do not enable verbose ASR/provider logging for private dialogue.

## Tests, packaging and review

```sh
./gradlew assembleDebug lintDebug testDebugUnitTest
cd apps/mac-translator
uv run ruff check .
uv run ruff format --check .
uv run mypy --config-file pyproject.toml src
uv run pytest -q
uv build
```
Optional real-model synthetic audio smoke (requires macOS `say` and both model servers):
```sh
uv run --project apps/mac-translator python scripts/ai_smoke.py
```
It saves fixture outputs/timings to `docs/evidence/ai-smoke.json`; these are synthetic
processing measurements, not microphone/gameplay latency.

Optional installed-emulator test, from repository root:
```sh
uv run --project apps/mac-translator python scripts/emulator_smoke.py --serial emulator-5556
```
It requires the debug APK installed, overlay permission granted and a landscape emulator;
uses run-as only to read the disposable emulator token, never prints it, and stops the
service afterwards. It is intentionally refused on physical devices.

The branch contains small milestone commits. No remote was configured during development;
[PR_DRAFT.md](PR_DRAFT.md) is ready to use with a GitHub draft PR after setting a remote.
APK and wheel packaging are local artifacts; CI builds APK and runs tests without making
physical-device claims. Review [test evidence](TEST_REPORT.md), [limitations](KNOWN_LIMITATIONS.md),
[architecture](docs/ARCHITECTURE.md), [decisions](docs/ADR.md), [status](docs/STATUS.md), and
[physical acceptance worksheet](docs/MANUAL_ACCEPTANCE.md).

## Troubleshooting

| Symptom | Next step |
|---|---|
| Draw-over screen missing | Optional ordinary `appops` grant in M0 guide; no root required |
| Local text visible, HDMI invisible | Record physical gate FAIL; use Mac viewer |
| 401 | Re-enter current TV token; app data reset rotates it |
| TV unavailable | Start Service from visible app; check LAN IP, isolation, firewall and port 8765 |
| LAN port unavailable in TV status | Stop/Start Service; check another app using 8765 |
| No microphone | Run devices; grant macOS permission; choose supported input |
| No captions with music | Tune threshold/volume/placement; energy VAD cannot isolate speakers |
| ASR startup failure | Start whisper-server and check URL/port/model; first Metal compilation takes time |
| Translation failure | Check Ollama model downloaded, server running, base URL and credentials |
| Captions lag behind | Model may be too slow; stale work is dropped; use smaller ASR model or faster provider |
| Service dies after standby | Reopen TV app and Start; there is deliberately no automatic boot start |

Stop capture with Ctrl-C and Stop Service on TV when finished. Remove the debug APK and
revoke debugging/overlay permissions using the M0 cleanup steps. Do not change PS5 or
Sony HDR/VRR settings as a workaround without separately recording the impact.

## Hybrid subtitles + speech + chat

Use `--input remote-play-hybrid --ocr-chat --ocr-phone` to capture both inputs with a single native stream. OCR takes priority; speech fills gaps. See [Hybrid setup and limitations](docs/HYBRID.md). Existing single-input modes remain available.

0.5.0 adds `leonida-tv-bridge`: forwards new captions from Leonida Mac's enabled LAN web viewer to Mac preview/optional existing TV overlay, with no library extraction or AI calls. 62 tests and mypy pass. Actual SSE connection verified; new gameplay captions and TV delivery still require verification. See docs/LEONIDA.md.

0.6.0 / TV APK 0.2.0: experimental actual-Leonida-audio relay via `leonida-tv-bridge --audio`, app-only native capture, 100ms PCM packets, authenticated bounded receiver, mute/enable controls and disconnect watchdog. 66 Python and 7 Android JVM tests pass; APK builds. Actual TTS capture and TV/HDMI playback remain unverified. See docs/LEONIDA_AUDIO.md.
