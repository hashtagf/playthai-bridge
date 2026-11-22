"""Loopback-only fallback: no token, captions or microphone data exposed to LAN."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .protocol import Caption


class Preview:
    def __init__(self, port=8766, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.text = ""
        self.deadline = 0.0
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Reject DNS rebinding and cross-origin browser reads.
                if self.headers.get("Host") not in (
                    f"127.0.0.1:{preview.port}",
                    f"localhost:{preview.port}",
                ):
                    self.send_error(403)
                    return
                if self.path == "/caption":
                    body = json.dumps({"text": preview.current()}, ensure_ascii=False).encode()
                    mime = "application/json; charset=utf-8"
                elif self.path == "/":
                    body = Path(__file__).with_name("viewer.html").read_bytes()
                    mime = "text/html; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.server.server_port

    def send(self, caption: Caption):
        with self.lock:
            self.text = caption.text
            self.deadline = self.clock() + caption.duration_ms / 1000

    def current(self):
        with self.lock:
            return self.text if self.clock() < self.deadline else ""

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
