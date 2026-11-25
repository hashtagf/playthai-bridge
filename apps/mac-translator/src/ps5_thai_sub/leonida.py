"""Forward new captions from Leonida's enabled LAN web viewer; never copy its library."""

import argparse
import json
import logging
import os
import queue
import threading
import time

import httpx

from .protocol import Caption
from .publisher import Publisher, lan_host
from .viewer import Preview

LOG = logging.getLogger("ps5-thai-sub")


class LiveTail:
    """Seed initial history silently, then emit only the newest newly appended entry."""

    def __init__(self):
        self.epoch = None
        self.count: int | None = None
        self.last = ""

    def observe(self, event):
        log = event.get("log")
        if not isinstance(log, dict):
            raise ValueError("Leonida event has no viewer log")
        count, start, items = log.get("n"), log.get("from"), log.get("items")
        if type(count) is not int or type(start) is not int or not isinstance(items, list):
            raise ValueError("Invalid Leonida viewer event")
        if count < 0 or start < 0 or start + len(items) != count:
            raise ValueError("Inconsistent Leonida viewer event")
        initial = self.count is None or self.epoch != log.get("epoch") or count < self.count
        added = not initial and self.count is not None and count > self.count
        self.count, self.epoch = count, log.get("epoch")
        if not items:
            return None
        newest = items[-1]
        if not isinstance(newest, dict) or not isinstance(newest.get("th"), str):
            raise ValueError("Invalid Thai viewer caption")
        text = newest["th"].strip()
        repeated = text == self.last
        self.last = text
        if not added or repeated or not text or not any("\u0e00" <= c <= "\u0e7f" for c in text):
            return None
        text = "".join(c for c in text if ord(c) >= 32 or c == "\n")
        return text.encode("utf-16-le")[:1000].decode("utf-16-le", errors="ignore")


def sse_events(lines):
    data: list[str] = []
    size = 0
    for line in lines:
        if not line:
            if data:
                yield json.loads("\n".join(data))
            data, size = [], 0
        elif line.startswith("data:"):
            value = line[5:].lstrip(" ")
            size += len(value)
            if size > 200_000:
                raise ValueError("Leonida event exceeds size bound")
            data.append(value)


class LeonidaStream:
    def __init__(self, host, port=8765):
        self.url = f"http://{lan_host(host)}:{port}/events"
        self.pending: queue.Queue[tuple[float, str]] = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.connected = False

    def _run(self):
        with httpx.Client(trust_env=False, timeout=httpx.Timeout(15, connect=3)) as client:
            while not self.stop.is_set():
                tail = LiveTail()  # Never replay old subtitles after reconnection.
                try:
                    with client.stream("GET", self.url) as response:
                        response.raise_for_status()
                        if "text/event-stream" not in response.headers.get("content-type", ""):
                            raise ValueError("Source is not Leonida web viewer")
                        self.connected = True
                        LOG.info("Leonida viewer connected; waiting for a NEW caption")
                        for event in sse_events(response.iter_lines()):
                            if self.stop.is_set():
                                return
                            if not isinstance(event, dict):
                                raise ValueError("Invalid viewer event")
                            text = tail.observe(event)
                            if text:
                                try:
                                    self.pending.get_nowait()
                                except queue.Empty:
                                    pass
                                self.pending.put_nowait((time.monotonic(), text))
                except (httpx.HTTPError, ValueError, TypeError):
                    LOG.warning("Leonida viewer disconnected or incompatible; retry in 2s")
                finally:
                    self.connected = False
                self.stop.wait(2)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=16)


def main():
    parser = argparse.ArgumentParser(description="Leonida live web captions → existing TV overlay")
    parser.add_argument("--source", required=True, help="Mac LAN IPv4 shown by Leonida web viewer")
    parser.add_argument("--source-port", type=int, default=8765)
    parser.add_argument("--target", help="TV LAN IPv4; omit for Mac preview only")
    parser.add_argument("--token", default=os.getenv("PS5_TV_TOKEN", ""))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--preview-port", type=int, default=8766)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    publisher = preview = None
    try:
        for port in (args.source_port, args.port, args.preview_port):
            if not 1 <= port <= 65535:
                raise ValueError("Invalid port")
        source = LeonidaStream(args.source, args.source_port)
        publisher = Publisher(args.target, args.token, args.port) if args.target else None
        preview = Preview(args.preview_port)
        LOG.info("Leonida bridge preview: http://127.0.0.1:%d (no AI translation)", preview.port)
        retry_at = 0.0
        with source:
            while True:
                try:
                    stamp, text = source.pending.get(timeout=0.5)
                except queue.Empty:
                    continue
                if time.monotonic() - stamp > 3:
                    continue
                caption = Caption.new(text)
                preview.send(caption)
                LOG.info("New Leonida caption received (content not logged)")
                if publisher and time.monotonic() >= retry_at:
                    try:
                        publisher.send(caption)
                        LOG.info("TV acknowledged Leonida caption")
                    except RuntimeError:
                        retry_at = time.monotonic() + 5
                        LOG.warning(
                            "TV unavailable; Mac preview active, old captions will not replay"
                        )
    except KeyboardInterrupt:
        LOG.info("Stopped Leonida bridge")
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Bridge failed: {error}\n")
    finally:
        if publisher:
            try:
                publisher.send(Caption.new(""))
            except RuntimeError:
                pass
            publisher.close()
        if preview:
            preview.close()
