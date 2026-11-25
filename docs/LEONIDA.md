# Leonida Mac application and live-caption bridge

LeonidaSubTH 1.7.1 was installed from the publisher-linked Mac release. macOS Screen
Recording is enabled and the application is configured for Remote Play. The app owns
OCR and translation; this bridge only displays new captions from its user-enabled LAN
web viewer. It does not access, copy, export or redistribute the translation library.
This is an unofficial adapter to the current viewer output, not an advertised stable API.
Publisher application: https://www.leonidasubth.com/mac

## Start

Enable **เปิดเว็บซับ + QR** in Leonida. Identify the Mac's reachable LAN IPv4. The app can
show a VPN interface address rather than the Wi-Fi address. On this setup 10.6.12.2 did
not respond, while 192.168.1.61 returned the Leonida viewer. Another unrelated service
already uses 127.0.0.1:8765, so do not assume localhost points to Leonida or stop that service.
The bridge requires a text/event-stream response and validates the viewer payload.

```sh
uv run --project apps/mac-translator leonida-tv-bridge --source MAC_LAN_IP
```

Mac preview: http://127.0.0.1:8766/. When on the home network and TV overlay is running,
export PS5_TV_TOKEN and restart with:

```sh
uv run --project apps/mac-translator leonida-tv-bridge --source MAC_LAN_IP --target TV_IP
```

Run one subtitle publisher at a time. Ctrl-C stops the bridge. Leonida remains running.
The existing TV APK is compatible; do not use Mac IP as TV IP. IPs may change between
networks. Remote Play can be used away from home if connected, but this LAN-only bridge
does not make the home TV reachable from elsewhere.

## Behavior and limits

- Reads the app's `/events` SSE endpoint. The initial viewer history and reconnect
  history seed the cursor silently; only newly appended captions are forwarded.
- For bursts, displays only the newest caption. Suppresses adjacent identical Thai
  strings; bounds payloads to 500 UTF-16 units. No saved dialogue or corpus.
- Caption expires after five seconds. This viewer-history adapter does not yet reproduce
  Leonida's exact on-screen hide timing or extend long messages until reading is finished.
- Reconnects source after failures, keeps latest pending item only, drops items older than
  three seconds, and backs off TV sends after failure. It does not replay missed captions.
- No AI calls, microphone recording or speech fallback in this mode. Keep the old hybrid
  command available if needed, but do not run both publishers simultaneously.
- Website terms restrict reuse/distribution of its library. No library is bundled here.
  Any broader integration/distribution needs clarification with the publisher.

## Verification (2026-11-25)

App launch and Screen Recording verified in UI. Main window reports Remote Play selected.
Real viewer returned HTTP 200 and `/events` returned text/event-stream with v/now/en/log/font;
initial log was empty. Running bridge connected successfully, with Mac preview available.
62 Python tests and mypy pass, including initial/reconnect replay prevention, duplicate
suppression, bounded output and SSE parsing. Live game captions and TV delivery remain
unverified: user is away from home, no new caption has yet been observed by the bridge.
