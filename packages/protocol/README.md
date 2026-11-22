# Caption protocol v1

HTTP/1.1 on TV TCP 8765. All endpoints require `Authorization: Bearer <pairing token>`.
`GET /health` returns 200 while server runs; it is not proof of on-screen visibility.
`POST /v1/captions`, Content-Type application/json, body per schema:
202 accepted into latest-wins UI slot; 200 duplicate; 400 invalid; 401 unauthorized;
403 non-LAN peer/browser Origin; 404 route; 413 body length. Empty text hides.
No remote input, HTML, file access, launcher changes, or command execution endpoints.

Expiry uses receiver monotonic time/Handler delay, not created_at. New messages replace
old captions. Duplicate ids do not refresh expiry. Dedup retains at most 256 ids for
60 seconds: unique ids are required and replay protection is bounded, not permanent.
Client retries the SAME id at most three attempts (1s per request, 150/300ms backoff).
Capture queue capacity is one; the newest completed utterance replaces waiting work.
No partial ASR captions, so partial revisions cannot flicker on TV.

TV binds IPv4 wildcard so Wi-Fi/Ethernet and emulator forwarding work; accepted peers
must be RFC1918/site-local or loopback, checked on the real socket (no forwarded headers).
No CORS, browser Origin rejected, 4 KiB headers, 8 KiB body, one worker, backlog four,
1s socket timeout and bounded read deadline. This limits resources but cannot prevent
LAN denial of service. Unencrypted HTTP is only for a trusted isolated home LAN: token
prevents accidental control, not eavesdropping. No Internet exposure or router forwarding.
Rotate by clearing app data/re-pairing. Production/untrusted networks need TLS or a tunnel.
TV needs inbound 8765 only from Mac; Mac viewer listens only on 127.0.0.1:8766.
