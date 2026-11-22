# Draft PR: Add PS5 Thai subtitle overlay and Mac speech pipeline

PS5 gameplay remains on direct HDMI while a Mac listens to TV dialogue and publishes
Thai captions to a user-started Android overlay. This proof of concept adds the M0
feasibility APK first, an authenticated LAN bridge, local Whisper/Ollama translation,
and a browser fallback when a TV blocks HDMI overlays.

## Changes

- Native Kotlin foreground service with transparent non-interactive Thai caption window,
  permission/start/stop/test/hide controls and text/opacity/safe-area presets.
- Token-authenticated, bounded LAN caption endpoint with deduplication and monotonic expiry.
- Python microphone/VAD pipeline, bounded queue, real ASR/translation adapters, context echo
  guard, demo fixtures, latency metrics, retries and packaged localhost viewer.
- Gradle wrapper, uv lockfile, CI, protocol schema, setup and physical acceptance worksheet.

## Validation

Android APK/build/lint pass (4 JUnit tests; 0 lint errors / 6 localization warnings).
Python: 21 tests, Ruff, mypy and wheel build pass. Fresh generic Android 16 emulator
verified Thai rendering over home, auth, duplicates, expiry, hide and listener shutdown.
Real whisper.cpp + Gemma 3 4B processed synthesized audio and published Thai to emulator.
Mac microphone startup and browser preview verified. See TEST_REPORT.md for exact scope.

![M0 emulator overlay](docs/evidence/emulator-m0.png)
![LAN emulator overlay](docs/evidence/emulator-lan.png)

## Required before hardware acceptance

BRAVIA 9 HDMI is **NOT TESTED**. Test local Thai text over PS5 first, then direct DualSense,
Game Mode/HDR/4K/VRR, standby/resume and real game audio quality/latency. If HDMI fails,
stop TV rollout and use Mac fallback. HTTP is trusted-LAN-only and is not encrypted.

## Publication status

Prepared locally on `feat/ps5-thai-subtitles`; no remote was configured, so no hosted PR
was opened and no CI run is claimed. After configuring the intended repository:

```sh
git push -u origin main
git push -u origin feat/ps5-thai-subtitles
gh pr create --draft --base main --head feat/ps5-thai-subtitles --title "Add PS5 Thai subtitle overlay and Mac speech pipeline" --body-file PR_DRAFT.md
```

No merge or deployment is part of this change.

## Follow-up: optional Remote Play OCR

Adds window-only ScreenCaptureKit capture and English Apple Vision OCR, configurable
subtitle crop, stability filtering, duplicate suppression, expiry renewal and stale-result
rejection. No microphone or Whisper dependency in OCR mode. Native helper builds on first
run and is included in the wheel as Swift source. 27 Python tests, native OCR/capture
fixture checks and synthetic OCR-to-TV smoke pass. Actual Remote Play game-session and
controller coexistence still require user connection and hardware verification.

Follow-up model choice: user-requested OpenThai default with `--model openthai`,
`--model gemma` and full model IDs; `models` reports presets/effective default.
CLI/environment priority tested; 33 Python tests pass. Switching takes effect on restart.

Follow-up v0.3.0: optional Remote Play application-audio input via ScreenCaptureKit,
without microphone/loopback driver. App inclusion filtering, checked 16kHz mono PCM,
bounded VAD buffering, privacy-safe signal telemetry and helper lifecycle cleanup.
Actual Remote Play nonzero audio verified; 40 Python tests. Model presets apply to all
three input modes. Audio/translation quality remains a separate acceptance check.
