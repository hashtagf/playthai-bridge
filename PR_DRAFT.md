# PlayThai Bridge: Mac subtitles and audio for Android TV

Adds a user-started Android TV overlay and authenticated LAN bridge so PS5 can remain on HDMI while a Mac supplies Thai captions. Inputs include Remote Play OCR, speech, combined OCR/speech with chat and phone regions, and Leonida live viewer captions. OpenThai is the default AI translator; providers remain configurable.

Experimental Leonida app-only audio capture sends bounded PCM packets to the TV with explicit enable/mute, session expiry and no stale packet retries. It does not redistribute Leonida or its translation library. The Thai README covers installation, pairing, source selection, troubleshooting and hardware limitations.

## Validation
- 66 Python tests; Ruff and mypy.
- 7 Android JVM tests; debug APK build and Android lint.
- Native capture helper compilation and earlier emulator/synthetic-model checks are documented in TEST_REPORT.md.

## Hardware checks outstanding
Actual Leonida TTS capture and audible TV playback while HDMI is active are not yet verified. Validate subtitle delivery from new Leonida lines, mute/disconnect handling, standby, ARC/eARC routing, real gameplay quality and end-to-end latency. LAN HTTP is not encrypted. This is a draft proof of concept, not a hardware acceptance claim.
