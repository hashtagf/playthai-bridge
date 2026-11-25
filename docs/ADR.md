# Architecture decisions

1. **Independent native app.** Implement WindowManager/TextView directly. ATV-Overlay's
README was read on 2026-11-22; no license was shown in its repository root, so no source
was copied. It explicitly warns some TVs block overlays. couch-tv declares MIT and is
reference-only: no launcher replacement or source copied. whisper.cpp declares MIT and
is an optional external runtime, not vendored. References:
[ATV-Overlay](https://github.com/Splinterjke/ATV-Overlay),
[couch-tv](https://github.com/Seagey/couch-tv),
[whisper.cpp](https://github.com/ggml-org/whisper.cpp).
2. **Foreground service specialUse.** User starts from visible Activity; target SDK 35,
SYSTEM_ALERT_WINDOW, non-focusable/non-touchable overlay, no boot receiver. Special-use
subtype is documented in manifest per [Android service types](https://developer.android.com/develop/background-work/services/fgs/service-types).
No claim of Play Store approval; this is a sideloaded debug proof of concept.
3. **Small HTTP subset.** No runtime Android networking dependency. Bounded single worker,
constant-time token comparison, peer filtering, plain text only; close each connection.
Review/fuzz further before hostile-network deployment. Clock-independent expiry, bounded
dedup and latest-wins delivery deliberately sacrifice old dialogue for responsiveness.
4. **Whisper server + compatible translation API.** whisper.cpp supports Apple Silicon
Metal and Intel CPU. Its [server interface](https://github.com/ggml-org/whisper.cpp/tree/master/examples/server)
accepts an in-memory WAV multipart request. Separate process permits warm model reuse.
Ollama provides local translation through its compatible chat API; another configured
provider can be used with explicit credentials. No Apple language-pair assumptions.
5. **No recordings by default.** Microphone samples stay in memory in this client; ASR
server/provider logging is separately controlled. Live text is absent from client logs.
Cloud configuration sends transcripts to the chosen provider; default is localhost.
Energy VAD/DC removal is lightweight but game music may trigger it. No denoising claim.
6. **Fallback built in.** Loopback browser preview always receives captions even if TV is
disconnected. It uses textContent, monotonic server expiry, Host validation and no CORS.
7. **Honest gate.** Automated/emulator results never establish BRAVIA HDMI support. If the
physical gate fails, stop TV rollout and use fallback rather than privileged workarounds.
