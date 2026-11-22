# Physical acceptance worksheet

BRAVIA 9 + PS5 HDMI gate: **USER-REPORTED PASS** (follow-up on 2026-11-22).
The user reports overlay visibility; the agent has not independently observed HDMI gameplay.
Do not infer PASS from an APK, emulator screenshot, health response or mocked translation.

Record date, tester, TV firmware, app commit/APK SHA256, macOS/architecture and connection method.
Keep PS5 → HDMI → BRAVIA and DualSense → PS5. No capture device or Remote Play required.

| Check | Outcome | Evidence / observations |
|---|---|---|
| Thai test visible in TV app, correct glyphs | NOT TESTED | |
| Thai visible over actual PS5 HDMI gameplay | USER-REPORTED PASS | User reports subtitle visible; no HDMI photo independently verified |
| DualSense continues controlling PS5 | NOT TESTED | |
| TV menus and HDMI switching recover | NOT TESTED | |
| Game Mode, HDR, 4K and VRR unchanged | NOT TESTED | |
| Standby/resume: caption expires, restart if service killed | NOT TESTED | |
| Authenticated LAN Thai caption, hide and expiry | NOT TESTED | |
| Stop service removes caption and closes port | NOT TESTED | |
| Microphone hears English dialogue at gaming volume | NOT TESTED | |
| Thai model translation judged by fluent reader | NOT TESTED | |
| Actual end-of-utterance latency p50/p95 | NOT TESTED | |

For the HDMI test, show the 30-second local Thai sample and switch inputs immediately.
Photograph actual PS5 image with caption and note firmware; repeat each video mode.
If local app succeeds but HDMI fails, record FAIL and stop TV-dependent rollout.
Use `ps5-thai-sub run --demo` and the Mac viewer as fallback. Separate display is
least invasive. Streaming to Mac adds latency and changes the viewing path. An external
HDMI compositor adds hardware cost and may affect HDR/VRR/HDCP; none is implemented here.
No protected-content interception, root patches, launcher replacement or firmware exploits.
