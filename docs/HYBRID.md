# Hybrid Remote Play translation (0.4.0)

## Plan and implementation

1. Capture window video and app audio from one ScreenCaptureKit stream. A separate serial
   Vision queue recognizes all configured regions from the same frame; audio continues on
   its own callback queue. No microphone, screenshots or audio files are saved.
2. Stabilize subtitle/chat/phone regions independently. Give phone text priority, then visible
   subtitle text. Block speech output immediately when subtitle/phone text appears, even
   while its translation is pending. Chat can coexist with speech fallback.
3. Run at most one OCR translation and one speech pipeline job concurrently. Each region
   and audio use separate translation context/clients. Drain and discard superseded audio;
   retain only the newest capture queue entry. There is no dialogue backlog.
4. A single main-thread arbiter publishes combined captions. Reject stale OCR generations,
   stale audio (>5s), and audio that ended before OCR's 800ms release grace period.
   Normalize and compare recent English text (8s window, similarity threshold 0.88 for
   longer phrases) to suppress repeated OCR/audio dialogue. Bound output to 500 UTF-16 units.
5. Validate automated arbitration and capture on the actual Mac/TV. Keep speech-only and
   OCR-only modes available for rollback.

## Run

```sh
uv run --project apps/mac-translator ps5-thai-sub ocr-windows
uv run --project apps/mac-translator ps5-thai-sub run \
  --input remote-play-hybrid --window-id WINDOW_ID \
  --ocr-chat --ocr-phone \
  --ocr-region 0.15,0.70,0.60,0.25 \
  --ocr-chat-region 0.79,0.77,0.20,0.21 \
  --ocr-phone-region 0.35,0.20,0.27,0.65 \
  --target "$TV_IP" --model openthai
```

Export PS5_TV_TOKEN as for other modes. Stop the old process before starting. Existing
TV APK is compatible. Use Screen & System Audio Recording permission; keep Remote Play
connected with its speaker enabled. Whisper and Ollama must already be running.

## Failure behavior and limits

- OCR snapshots older than 3s expire; speech fallback remains eligible. Capture process
  failure terminates the run with an actionable error. It is not an automatic reconnecter.
- Translation errors retry OCR after 2s, skip failed speech, and do not log dialogue content.
- Ctrl-C waits for bounded in-flight HTTP requests to finish, closes capture and clears TV.
- Phone detection remains a text-density heuristic, not a visual phone detector. HUD text
  in the subtitle crop can suppress speech; adjust crops for each game.
- Speech gating reduces noise but cannot separate voices, singing, music or effects.
- Similarity matching is approximate; partial OCR, differing transcription and legitimate
  repeats can cause misses or false suppression. Long chat can be truncated.
- Two simultaneous model requests may increase latency. This release is not a measured
  speed improvement, nor proof of accurate translation. OpenThai remains the default.

## Evidence

58 Python tests pass, including priority, in-flight stale result rejection, expiry,
chat/audio coexistence, duplicate suppression, phone transitions, bounded payloads,
and the hybrid runner's publication and shutdown path. Native helper builds on the Mac.
Actual hybrid session observed fresh OCR (0.0–0.3s age), increasing audio frames (502 then
1002), accepted subtitle and chat translations, and authenticated TV acknowledgements.
This proves concurrent capture and OCR publication; it does not prove audible speech
quality or live fallback transitions. Real gameplay with speech without subtitles,
phone open/close, music-only sections and long-run stability still needs verification.
