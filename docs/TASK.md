# Codex implementation task — PS5 → Mac AI Thai subtitles → Sony BRAVIA 9 overlay

## ROLE
You are the primary software engineer. Work in a NEW, dedicated repository chosen by the user (do not modify upstream open-source repositories). Build a runnable proof of concept, not just a proposal. Work in small commits and show build/test evidence. Do not claim an actual BRAVIA 9 HDMI overlay has been verified unless tested on the physical TV.

## USER / PROBLEM
- Hardware: Sony PlayStation 5, Sony BRAVIA 9 Google TV, Mac, iPhone, DualSense controller.
- Desired: Play PS5 games on the BRAVIA 9 via ordinary HDMI with the DualSense connected DIRECTLY to PS5, while Thai translated subtitles appear as a transparent overlay on the same TV.
- Avoid: TranslaCat subscription, mandatory Android phone, PS Remote Play requirement, buying HDMI capture hardware for MVP, disrupting HDR/4K/VRR/gameplay controls.
- Primary input in MVP: Mac microphone listens to English dialog played by Sony TV. Output: Thai text on the TV. Text-only OCR (requiring video capture) is future scope.
- Important unknown: Does BRAVIA 9 render a third-party Android overlay while HDMI input is active? Make this the FIRST go/no-go physical-device experiment. Provide a fallback subtitle viewer on Mac if the TV blocks HDMI overlay.

## OPEN SOURCE REFERENCES (read, verify licenses, do not assume device compatibility)
- https://github.com/Splinterjke/ATV-Overlay — proof-of-concept Android TV native overlay using HTTP API; its README documents `POST /overlay`, `SYSTEM_ALERT_WINDOW`, and the limitation that some TVs block overlays. Its development HTTP endpoint has no authentication. Use only for isolated LAN testing, not production. Check licensing before copying any code; if license is unspecified, do not copy code.
- https://github.com/Seagey/couch-tv — Android TV home screen with a doorbell overlay; reference only, do NOT replace the Sony TV launcher or require privileged ADB operations beyond an optional documented permission workaround.
- https://github.com/ggml-org/whisper.cpp — potential local speech recognition backend for Apple Silicon via Metal/Core ML.
- Apple Speech / Translation, Ollama or OpenAI-compatible translation service are alternatives; choose a working path based on development environment and explain tradeoffs.

## MVP IMPLEMENTATION ORDER — STOP IF HARDWARE BLOCKED

### M0 — physical-device overlay feasibility gate (priority 1)
1. Create a small, independent Android TV Kotlin application (`tv-overlay`) using Android SDK; launcher Activity includes visible controls to request overlay permission, start/stop a foreground overlay service, enter Mac IP if needed, view service status and show/hide test text. Do not install a replacement launcher.
2. Use `WindowManager` with `TYPE_APPLICATION_OVERLAY`, `FLAG_NOT_FOCUSABLE`, `FLAG_NOT_TOUCHABLE`, appropriate TV-compatible foreground-service handling, and an entirely transparent background outside the caption region. Caption must be legible in Thai, centered near the bottom, and configurable for text size / background opacity / safe area. Render plain text, not untrusted HTML.
3. Add a hard-coded local Thai test string: `เราต้องออกจากที่นี่ก่อนรุ่งสาง`.
4. Provide a debug APK build task, installation via `adb install`, guide for Android TV network/USB debugging, required settings screens, permission prompts and restoring disabled settings afterwards.
5. Physical test protocol: BRAVIA 9 with PS5 on HDMI → start overlay → switch to HDMI → verify text is visible over actual PS5 video and that DualSense still controls PS5; then test switching menus, Game Mode, HDR and standby/resume. Record a pass/fail worksheet.
6. If overlay is blocked, do NOT falsely mark complete. Implement the fallback Mac browser subtitle viewer, document results, and describe the least-invasive alternatives (external HDMI compositor, streaming video to Mac, separate display).

Acceptance: APK builds; can show Thai overlay on Android TV / emulator (where permitted); test instructions are reproducible; physical HDMI result explicitly labeled `NOT TESTED / PASS / FAIL`.

### M1 — LAN caption bridge
1. Mac CLI sends simple structured caption messages to the Android TV app, and the TV shows/hides them. A local transport is enough (HTTP or WebSocket). Use automatic expiry so stale captions disappear after a few seconds.
2. Use `POST /v1/captions` accepting JSON `{id, text, language:"th", duration_ms, created_at}` plus `GET /health`. Include client timeout, retries with backoff, caption deduplication, backpressure, and clock-independent expiry.
3. Do not expose an open unauthenticated TV remote-control server: include a shared pairing token, input validation, bounded text length, LAN-only access and clear warnings for any debug-only mode. Bind to an appropriate interface and document firewall implications.
4. Add a Mac command `send-test-caption --tv-host <IP> --token <TOKEN> --text "..."`.
5. Include unit/integration tests for auth failure, Thai UTF-8, duplicate ids, expiry, and lost TV connection.

Acceptance: Sending Thai text from Mac to the TV works while the TV app is active; caption update/hide behavior is demonstrated at least on an emulator; real HDMI verification remains an explicit separate step.

### M2 — Mac English speech → Thai translation
1. Create Mac-hosted Python 3.12+ project (`mac-translator`) with clean architecture:
   - microphone/audio capture (no Remote Play, no PS5 exploit)
   - VAD / buffered chunks / optional noise filtering
   - transcriber interface (start with a feasible local Whisper backend for actual Mac architecture; allow mock mode in CI)
   - translator interface (`en`→`th`): a working local or configurable API provider; preserve proper names; no hallucinated text; phrase-level context window; optional translation cache
   - caption stabilizer (avoid duplicated repeated partials, avoid flicker)
   - LAN caption publisher
   - debug Mac subtitle viewer or localhost browser preview
2. CLI: `ps5-thai-sub run --input microphone --target <TV_IP> --token <PAIRING_TOKEN> --transcriber <...> --translator <...>`. Also support `--demo` with canned English dialog, working without model downloads or API keys.
3. Do not assume Apple Translation provides a particular language pair on every OS/device. Check runtime availability, or use a fully documented alternative provider.
4. Add `.env.example`, a real dependency lockfile, graceful errors, no saved microphone recordings by default, runtime logs with privacy-safe redaction, and startup device/permission checks.
5. Provide English sample phrases and Thai expected/reference outputs for deterministic translation unit tests; distinguish test mock translations from AI model performance.
6. Measure end-of-utterance-to-caption latency (p50/p95) on actual Mac where possible; treat <= 3 sec median as an aspirational target, not a claim.

Acceptance: Demo mode sends Thai captions to the TV without model/API; microphone mode works when a supported recognizer and translator are configured; tests pass; README contains exact setup/run commands for macOS Apple Silicon and flags Intel/macOS-specific caveats.

### M3 — integration, UX and packaging
1. Provide a single setup guide for BRAVIA 9 + Mac with screenshots optional, commands tested, error troubleshooting, permissions and firewall notes.
2. Output APK, Mac runnable CLI, the fallback Mac subtitle viewer, source code, README, architecture diagram, `TEST_REPORT.md`, `KNOWN_LIMITATIONS.md`, `ADR.md` and task/status checklist.
3. Prefer small CI jobs: Android Gradle assemble/lint/test, Python lint/types/pytest, no device-test claims.
4. Explicitly distinguish automated passing tests from physical PS5 + BRAVIA 9 verification. Provide manual acceptance checklist.
5. No DRM bypass, no protected HDMI interception, no sideloading privileged system patches, no exploitation of PlayStation firmware, no unattended deployment.

## PROJECT STRUCTURE (suggestion)
```
apps/tv-overlay/          # Android TV Kotlin app + overlay service
apps/mac-translator/      # Python Mac audio, VAD, ASR, translation, publisher
apps/mac-viewer/          # fallback viewer (optional simple local web app)
packages/protocol/        # JSON schemas and sample payloads
docs/                     # architecture, setup, manual test plan, decisions
.github/workflows/        # automated build/test
```

## DEFINITION OF DONE
- `./gradlew assembleDebug` generates Android TV APK (in the project and CI).
- Python app installs and `--demo` outputs Thai subtitles without network AI service.
- Test client can send Thai text through authenticated LAN transport, with expiration and no remote input interception.
- There is an accurate and repeatable BRAVIA 9 HDMI overlay checklist with outcome recorded (not guessed).
- PS5 controller remains paired to console; PS5 remains connected directly via HDMI.
- Show exact files changed, commands run, tests passing/failing, unverified hardware-dependent items and next actions. Open PR instead of merging/deploying automatically.

## CODING INSTRUCTIONS
1. First inspect the repository and environment (Mac architecture unknown; Android Studio/JDK availability unknown). If empty, scaffold it.
2. Start implementation immediately with M0 (not an essay-only plan). Build/tests where environment permits. Continue to M1 and demo mode in M2 if possible, but do not hide M0 blockers.
3. Prefer robust, small libraries and idiomatic Android architecture. Avoid copying ATV-Overlay source when its license cannot be verified; instead implement native overlay from Android SDK documentation.
4. Never hardcode secrets, IPs or personal information. Do not ask to purchase hardware for M0/M1.
5. Produce a draft PR with a concise implementation summary, screenshots/emulator output where possible and test evidence. If no GitHub remote is configured, prepare a local branch/patch and report the blocker.

## FIRST USER-VISIBLE DELIVERABLE
The FIRST deliverable should be a BRAVIA 9 overlay test APK + exact install/test instructions, including a one-screen UI with 'Show Thai Test Subtitle' and 'Hide Subtitle', NOT a completed AI engine promised without physical verification.
