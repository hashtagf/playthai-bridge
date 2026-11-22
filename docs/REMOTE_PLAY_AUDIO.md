# Remote Play app audio → Thai subtitles

Input mode `remote-play-audio` captures the selected application's system audio with
Apple ScreenCaptureKit. It feeds the existing VAD → local Whisper → selected translator
(OpenThai default) → TV/preview pipeline. It does not use the Mac microphone and does
not require BlackHole, loopback drivers or PS5 controller changes. The TV APK is unchanged.

## Run

Connect PS Remote Play to PS5 and **enable its speaker audio on Mac**. TV speaker volume
alone is irrelevant to this mode. Keep Whisper server and Ollama running (README setup).
From repository root, with TV_IP and PS5_TV_TOKEN exported:

```sh
uv sync --project apps/mac-translator --locked
uv run --project apps/mac-translator ps5-thai-sub capture-permission
uv run --project apps/mac-translator ps5-thai-sub audio-check --seconds 5
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-audio --target "$TV_IP" --model openthai
```

Switch translation model with `--model gemma`. Select OCR instead with
`--input remote-play-ocr`, or microphone with `--input microphone`. Run one input process
at a time. Ctrl-C stops capture, terminates the native helper, and clears captions.

Requires macOS 14+, Xcode Command Line Tools, and Screen & System Audio Recording
permission for the launching app/terminal. No microphone permission is required.
`capture-permission` is also available under the older `ocr-permission` name.

## Capture and buffering

- Strict application inclusion filter, default bundle ID `com.playstation.RemotePlay`.
  `--audio-app BUNDLE_ID` explicitly selects another app. Missing/ambiguous apps fail
  closed; the helper never falls back to capturing all system audio.
- ScreenCaptureKit performs conversion to 16kHz, mono, float32. The native callback checks
  the actual format; mismatches fail rather than silently misinterpreting PCM samples.
- Microphone capture is disabled. Minimal 2×2 video callbacks are discarded in the helper;
  no screenshots are exported or stored. Only PCM samples cross the process pipe.
- Audio stays in memory; the client writes no recordings/transcripts. External Whisper
  server logging is separately controlled and may include recognized text.
- A reader thread continuously drains the bounded OS pipe. PCM byte fragmentation is
  reconstructed into 320-sample/20ms frames. The VAD queue keeps only the newest pending
  utterance while transcription/translation is busy.
- Default RMS gate 0.006 (`--vad-threshold` can override), 300ms silence, at least 200ms
  voiced energy, 100ms pre-roll and a 2-second max chunk for continuous game sound.
  The microphone path retains its old 0.015 gate / 8-second cap.
- An aggressive WebRTC speech detector now gates the energy VAD before ASR. This is not dialogue isolation. Music/effects can still trigger false speech and
  Whisper can hallucinate. Lower threshold may hear quiet speech but also more game noise.

## Diagnostics and limitations

`audio-check` reports received frame count, number of frames above the energy gate and
peak amplitude. It does not transcribe, save or play captured audio. Above-threshold
frames prove a signal, NOT clear speech. Routine logs show counts/levels every ten seconds,
not dialogue content. Native permission/failure/EOF stops the process with a clear error.

If peak stays zero: unmute/raise Remote Play's speaker volume, confirm its game stream is
connected and audibly playing on Mac, and check macOS capture permission. Some mute/output
settings may silence the stream; don't assume capture bypasses application mute.

Remote Play app audio contains game music, effects and any chat mixed by that app. Filtering
by app is not speaker separation. Direct DualSense→PS5 coexistence and gameplay latency
remain device/session-dependent; no automatic account switching/re-pairing is performed.

## Verified on development Mac

- Native ScreenCaptureKit audio helper compiles on macOS 26.7 / Apple Silicon.
- First 5-second actual Remote Play test: 253 frames, zero peak (app was silent).
- After user reconnected: 256 frames, 57 above threshold, peak 0.0720. Actual nonzero
  Remote Play audio reached the 16kHz mono Python pipeline without the microphone.
- Whisper/Ollama readiness and TV authenticated health 200 checked before starting live run.
- 40 Python tests pass, including pipe fragmentation, invalid samples, silence, bounded
  queue, 4-second cap, source failure/EOF and helper cleanup. Ruff and mypy checked.
- Speech fidelity, translation accuracy and end-to-end gameplay latency need real usage;
  nonzero audio alone is not a quality acceptance pass.

References: [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos).
Implementation signatures verified against the installed macOS SDK headers.

Live app-audio run: two real captured-audio utterances completed Whisper → OpenThai → authenticated TV acknowledgement; end-of-utterance-to-ack 0.56–0.60 seconds. This excludes utterance collection time and panel rendering, and does not establish transcription/translation accuracy. No dialogue content was included in the client log.

## Speech filtering (0.3.1)

Remote Play audio now requires both energy and WebRTC VAD mode 3 speech detection before
counting a frame as voiced. Explicit bracketed/parenthesized sound cues and music-note
lyrics are stripped before translation; unmarked sound labels are skipped. Mixed dialogue
retains spoken text outside cues. Parenthesized spoken asides can also be removed by this
conservative rule. OCR remains a separate selectable input, not simultaneously merged.
This does not separate speakers or guarantee rejection of singing/music and effects.
Strict detection may miss quiet or very short dialogue. Real-game acceptance is still needed.
Reference: https://github.com/daanzu/py-webrtcvad-wheels

## Latency tuning (0.3.2)

App audio now finalizes after 300ms without detected speech (previously 500ms), and caps
collection at 2 seconds (previously 4). Strict speech detection and OpenThai stay enabled.
Shorter chunks can split sentences and reduce translation context. Timing logs now separate
chunk duration, wait after last voiced frame, ASR, translation and TV acknowledgement.
Existing post-utterance latency is not total latency from the start of dialogue.
49 tests pass, including 2-second cap and 300ms silence boundary. Real-game timing and
sentence quality need observation; these settings do not guarantee a latency target.
