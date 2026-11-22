# Test report — 2026-11-22

**Physical BRAVIA 9 + PS5 HDMI: NOT TESTED.** No physical TV/PS5 was attached.

Environment: Apple Silicon M4 Max, macOS 26.7 arm64; Python 3.12.8; Android SDK 35;
Gradle 8.11.1; Android Studio bundled JDK; generic Android 16/API 36 arm64 emulator.
The emulator uses a phone system image at 1920×1080 / 160dpi, not Sony/Android TV firmware.

| Verification | Result |
|---|---|
| `./gradlew assembleDebug lintDebug testDebugUnitTest` | PASS; APK built; 4 JUnit tests; lint 0 errors, 6 localization warnings |
| `uv sync --locked` | PASS; uv.lock resolves 24 packages |
| `uv run pytest -q` | PASS; 21 tests |
| `uv run ruff check .` / `ruff format --check .` | PASS |
| `uv run mypy --config-file pyproject.toml src` | PASS; 8 source files |
| `uv run ps5-thai-sub run --demo --demo-once` | PASS; three Thai fixture captions; no microphone or AI used |
| Demo with emulator target via ADB-forwarded TCP | PASS; authenticated health 200; all three captions acknowledged |
| `scripts/emulator_smoke.py --serial emulator-5556` | PASS; local test, background rendering, 401 auth, UTF-8, dedup, real WindowManager expiry/hide, Stop closes listener |
| Browser fallback | PASS; HTTP 200 and Thai text observed in BrowserOS; host/expiry tests automated |
| `uv build` | PASS; wheel and sdist; wheel includes viewer.html |
| `ps5-thai-sub devices` | PASS; Core Audio lists built-in microphone |
| Microphone open/close | PASS; 300ms in-memory 16kHz mono capture; no recording saved or content logged |
| Actual Whisper ASR | PASS; whisper.cpp 1.9.5 / base.en transcribed synthesized English |
| Actual AI → emulator transport | PASS; Gemma 3 4B via Ollama, three synthetic English samples; see JSON |
| Actual game audio accuracy / TV speaker pickup | NOT TESTED |
| Physical HDMI, HDR, VRR, Game Mode, DualSense, standby | NOT TESTED |
| Hosted GitHub Actions / draft PR | NOT RUN / NOT OPENED; no remote configured |

## Real-model smoke, not microphone latency

[scripts/ai_smoke.py](scripts/ai_smoke.py) uses macOS `say` to create disposable **synthetic**
WAV files, then calls real Whisper ASR and real Gemma translation and publishes to the
emulator. The client microphone path never writes recordings. No cloud keys were used.

Recorded warm processing-only p50 **0.196s**, p95 **0.211s**,
**n=3** on this Mac. This tiny synthetic sample excludes microphone capture, VAD silence
wait and physical display rendering. It does NOT establish the ≤3s gameplay median goal.
Actual end-of-utterance-to-caption p50/p95 remains NOT TESTED; the runtime logs that metric
at publish acknowledgement, not actual panel composition. See [raw fixture evidence](docs/evidence/ai-smoke.json).

Model smoke output differs from golden mock translations; exact golden equality is not
required of an AI model. No fluent-reader/game-dialogue acceptance is claimed.

## Problems found and resolved

- Existing emulator stayed RUNNING_LOCKED and could not launch installed apps. A separate
  disposable AVD was created; original AVD data was not wiped. Fresh AVD launched correctly.
- Homebrew whisper-server 1.9.5 did not accept upstream-master `--no-context`; tested command
  omits it. Do not assume master documentation exactly matches an installed release.
- TV shutdown can close HTTP mid-response. Publisher now retries TransportError (including
  RemoteProtocolError); regression test covers bounded retry and preserves caption ID.
- A single JSON context message confused a model and repeated earlier dialogue. Replaced
  with explicit user/assistant translation history plus current user line. A conservative
  echo guard skips repeated previous translations; regression test covers this. The final
  three-sample smoke translates all current lines, but broader hallucination risk remains.
- Qwen 1.5B and 7B produced awkward Thai in exploratory tests. Gemma 3 4B is the documented
  default. Rejected Qwen downloads were removed; Gemma and base.en remain for use.

## Evidence and artifacts

- [M0 Thai overlay over emulator home](docs/evidence/emulator-m0.png)
- [Authenticated LAN overlay](docs/evidence/emulator-lan.png)
- [Real AI samples and timing](docs/evidence/ai-smoke.json)
- APK: `artifacts/tv-overlay-debug.apk` (also normal Gradle output).
- SHA256: `9563f95011b890877527ac6069633dc5758287b5f890148a0632e001f5640acd`
- Python wheel: `artifacts/dist/ps5_thai_sub-0.1.0-py3-none-any.whl`.
- Source/patch handoff: `artifacts/ps5-thai-subtitles-handoff.zip` after final packaging.

Gradle detailed reports are under `apps/tv-overlay/build/reports/`. Screenshots show a
generic Android home screen, never a claimed BRAVIA HDMI result. Manual worksheet:
[docs/MANUAL_ACCEPTANCE.md](docs/MANUAL_ACCEPTANCE.md).

## Local environment changes

Installed whisper.cpp via Homebrew (including dependency installation/upgrades reported
by Homebrew), downloaded base.en into ignored artifacts/models, and Gemma 3 4B into
Ollama's local model store. uv environment and Gradle outputs are ignored. Test servers
and disposable emulator are stopped at handoff; existing Ollama service remains running.
