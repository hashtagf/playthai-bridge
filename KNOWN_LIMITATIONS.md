# Known limitations

- **BRAVIA 9 HDMI NOT TESTED.** A generic Android 16 emulator shows Thai over its home
  screen; it is not an Android TV firmware test and cannot reproduce an HDMI plane.
- Actual PS5 gameplay, direct DualSense control, Game Mode/HDR/4K/VRR, TV standby/resume,
  Sony permission screens, network debugging and physical LAN transport remain manual.
- Actual TV-speaker → microphone → AI → physical TV latency/accuracy is not measured.
  Microphone opens on this Mac; synthetic audio/model smoke results are a separate test.
- Local translation quality varies. The small Qwen models tested produced awkward Thai;
  successful inference is not human-rated accuracy. Proper-name preservation and no
  hallucination are prompt constraints, not provable guarantees. Real game audio, music,
  overlap and names need fluent-reader evaluation.
- A conservative context-echo guard skips a new line if it contains a prior full translation.
  This can reject legitimate repeated wording and cannot detect paraphrased hallucinations.
- Energy VAD (RMS + DC removal) is not learned speech/noise separation. 500ms silence,
  200ms minimum voiced audio, 100ms pre-roll, 8s maximum chunks, one pending utterance.
  No resampling; selected mic must support 16kHz mono. Long inference can drop dialogue.
- Caption length is bounded to 500 UTF-16 code units and four visual lines. Very long
  captions may clip at large font sizes. Thai uses Android's system fallback font.
- HTTP token is plaintext on the wire. Private-source filtering is not encryption or
  robust protection from malicious LAN peers. No WAN exposure. IPv4-only client.
- Dedup is bounded to 256 ids / 60 seconds; no persistent sequence ordering across Mac
  processes. Run one publisher. Only one latest caption is displayed.
- 202 means accepted into the UI slot, not rendered. `/health` tests listener availability,
  not overlay permission or HDMI visibility. Runtime failures appear in TV UI status.
- OEM foreground-service killing and protected surfaces may suppress the overlay. No
  privileged workarounds, auto-boot or battery-optimization exemptions are installed.
- Debug APK signing only. Not Play-reviewed, production hardened, fuzzed or audited.
- Optional ASR/Ollama dependencies and models are installed separately from uv.lock;
  model licenses are separate. Runtime server logging can contain recognized speech.
- No OCR/video capture, HDMI compositing, protected-content handling or Remote Play path.
- GitHub draft PR publication and CI execution require a configured remote; local draft,
  branch, patch and build/test evidence are supplied instead.
