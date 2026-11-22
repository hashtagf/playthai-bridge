# Remote Play subtitle OCR (macOS)

This is an optional input mode added at the user's request. The original microphone
path remains available. TV APK/protocol is unchanged; no reinstall is needed.

## Setup

1. Install Sony [PS Remote Play for Mac](https://remoteplay.dl.playstation.net/remoteplay/lang/en/1100002.html).
   This session installed the notarized Sony package in `~/Applications/RemotePlay.app`.
2. On PS5 enable Settings → System → Remote Play → Enable Remote Play. Sign into Remote
   Play on Mac and connect the PS5. Account sign-in must be completed by the user.
3. Enable **English subtitles in the game**. Keep the game video window open, not minimized.
4. Keep TV overlay service running. Keep Ollama running with `openthai/openthai-1.5-7b` downloaded (default), or select `--model gemma`.
   Whisper and microphone permission are not needed for this mode.
5. From repository root:

```sh
uv sync --project apps/mac-translator --locked
uv run --project apps/mac-translator ps5-thai-sub ocr-permission
uv run --project apps/mac-translator ps5-thai-sub ocr-windows
```

If requested, allow the launching app/terminal in System Settings → Privacy & Security →
Screen & System Audio Recording (label varies by macOS), then restart it. The OCR helper
requires macOS 14+ and Xcode Command Line Tools (`xcode-select --install`). It compiles
once into `~/Library/Caches/ps5-thai-sub`, keyed by source hash. No third-party OCR service.

Set TV_IP and PS5_TV_TOKEN as described in README, then run:

```sh
uv run --project apps/mac-translator ps5-thai-sub run   --input remote-play-ocr --target "$TV_IP"   --ocr-region 0.10,0.65,0.80,0.28
```

One visible Remote Play window is automatically selected. For multiple windows, use
`--window-id ID` from `ocr-windows`. IDs change when windows close/reopen. Explicit IDs
can select other applications for testing; never select an unrelated private window.

`--ocr-region x,y,width,height` uses fractions of the captured window with a **top-left**
origin. Default: middle 80% width, from 65% to 93% down. Adjust for letterboxing and the
game's subtitle position. Cropping is essential: menus, HUD labels and prompts inside
that region can be mistaken for subtitles. No automatic game/layout detection exists.

## Behavior

- ScreenCaptureKit captures only the selected window; Vision reads only the cropped region.
  Full selected-window pixels temporarily exist in native memory before cropping, never
  other windows. No image files or OCR transcripts are saved by normal operation.
- English OCR, confidence threshold 0.6, language correction disabled to preserve names.
- Requires two or more observations stable for 0.6 seconds; poll interval 0.3 seconds.
  Both are configurable (`--ocr-stable-seconds`, `--ocr-interval`). Very brief or animated
  subtitles can be missed; OCR errors/stream compression remain possible.
- Unchanged text is translated once; displayed caption refreshes every three seconds
  while source text remains. Blank source hides captions after stabilization.
- After translation the window is recaptured: if the source changed/disappeared, obsolete
  translation is discarded. No frame queue or saved screenshot backlog.
- Closing/minimizing the selected window or capture failure stops with a clear error,
  and the CLI attempts to clear the TV. Restart after reconnecting/selecting a new window.
- Ctrl-C stops capture and clears the caption. Mac preview remains at 127.0.0.1:8766.
- A frozen Remote Play stream cannot reliably be detected from unchanged subtitle pixels;
  disconnect dialogs can also resemble text. Stop capture when disconnected. No claim of
  accuracy, protected-content capture support, or improved latency until actual-game tests.

Sony's documented Mac workflow connects the controller to Mac. Continuing to use direct
DualSense → PS5 while Remote Play supplies only video is a separate physical test; it is
not guaranteed by this implementation. Do not silently re-pair the user's controller or
change console accounts. If that setup disconnects Remote Play, report it and choose the
control arrangement explicitly with the user. HDMI/HDR/VRR coexistence also needs testing.

## Validation performed

- Native Swift helper compiled on macOS 26.7 / Apple Silicon.
- Apple Vision recognized an in-memory synthetic English caption exactly.
- ScreenCaptureKit captured a temporary native test window; bottom-region crop excluded
  a top-of-window decoy and recognized the expected subtitle.
- Real capture/crop/OCR → Gemma → physical TV HTTP acknowledgement passed using synthetic
  text. This is not a Remote Play game-session verification.
- Python tests cover ROI validation, stable text, partial updates, no repeated translation,
  renewal, blank clearing, same line reappearing and changes during translation.
- Actual Remote Play game capture/controller coexistence: **PENDING user sign-in/connect**.

References: [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager),
[Apple Vision](https://developer.apple.com/documentation/vision/vnrecognizetextrequest).
