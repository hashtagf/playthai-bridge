"""Low-backlog PCM relay of Leonida's actual app audio; no synthesis or microphone."""

import argparse
import base64
import logging
import queue
import threading
import time
import uuid

import httpx
import numpy as np

from .publisher import lan_host
from .remote_audio import RemotePlayAudio

LOG = logging.getLogger("ps5-thai-sub")
LEONIDA_APP = "th.leonidasub.app"


class LeonidaAudio(RemotePlayAudio):
    def __init__(self, binary=None):
        super().__init__(app=LEONIDA_APP, binary=binary)
        self.packets: queue.Queue[tuple[float, bytes]] = queue.Queue(maxsize=2)
        self.pcm = bytearray()

    def ingest(self, data):
        # No speech VAD: preserve Thai TTS consonants, pauses and complete audio waveform.
        for frame in self.framer.feed(data):
            self.frames += 1
            self.peak = max(self.peak, float(np.max(np.abs(frame))))
            self.pcm.extend((frame * 32767).astype("<i2").tobytes())
            if len(self.pcm) == 3200:
                packet = (time.monotonic(), bytes(self.pcm))
                self.pcm.clear()
                if self.packets.full():
                    try:
                        self.packets.get_nowait()
                        self.dropped += 1
                    except queue.Empty:
                        pass
                self.packets.put_nowait(packet)


def payload(action, session, sequence, pcm=None):
    body = {
        "action": action,
        "session": session,
        "sequence": sequence,
        "sample_rate": 16000,
        "channels": 1,
        "format": "s16le",
    }
    if action == "chunk":
        if pcm is None or len(pcm) != 3200:
            raise ValueError("PCM must be exactly 100ms mono PCM16")
        body["pcm"] = base64.b64encode(pcm).decode("ascii")
    return body


class AudioRelay:
    def __init__(self, host, token, port=8765, capture=None):
        if len(token) < 24:
            raise ValueError("TV pairing token required for audio")
        self.url = f"http://{lan_host(host)}:{port}/v1/audio"
        self.capture = capture or LeonidaAudio()
        self.client = httpx.Client(
            trust_env=False, timeout=0.35, headers={"Authorization": f"Bearer {token}"}
        )
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def send(self, action, session, sequence, pcm=None):
        response = self.client.post(self.url, json=payload(action, session, sequence, pcm))
        if response.status_code in (401, 403, 404):
            raise ValueError("TV audio unavailable: check APK version and pairing token")
        response.raise_for_status()

    def _run(self):
        session = ""
        sequence = 0
        next_try = 0.0
        last_report = time.monotonic()
        sent = 0
        try:
            while not self.stop.is_set():
                if self.capture.error:
                    raise RuntimeError(self.capture.error)
                try:
                    stamp, pcm = self.capture.packets.get(timeout=0.1)
                except queue.Empty:
                    continue
                now = time.monotonic()
                if now - stamp > 0.25 or now < next_try:
                    continue
                try:
                    if not session:
                        session = uuid.uuid4().hex
                        sequence = 0
                        self.send("start", session, sequence)
                        LOG.info("TV audio session ready")
                    if time.monotonic() - stamp > 0.25:
                        continue
                    sequence += 1
                    self.send("chunk", session, sequence, pcm)
                    sent += 1
                except httpx.HTTPError:
                    # Never retry a PCM chunk: a delayed replay is worse than a brief gap.
                    session = ""
                    next_try = time.monotonic() + 1
                    LOG.warning("TV audio disconnected/disabled; dropping audio until reconnect")
                if now - last_report >= 10:
                    LOG.info(
                        "Audio relay chunks=%d dropped=%d peak=%.3f",
                        sent,
                        self.capture.dropped,
                        self.capture.peak,
                    )
                    if self.capture.peak < 0.0001:
                        LOG.warning(
                            "No Leonida audio detected; enable read-aloud and test its voice"
                        )
                    last_report = now
        except (ValueError, RuntimeError, OSError) as error:
            self.error = str(error)
            LOG.error("Audio relay stopped: %s", self.error)
        finally:
            if session:
                try:
                    self.send("stop", session, sequence + 1)
                except (httpx.HTTPError, ValueError):
                    pass  # TV watchdog also expires the stream without the sender.

    def __enter__(self):
        try:
            self.capture.__enter__()
            self.thread.start()
        except BaseException:
            self.capture.close()
            self.client.close()
            raise
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)
        self.capture.close()
        self.client.close()


def check_main():
    parser = argparse.ArgumentParser(
        description="Check actual Leonida app audio without saving recordings"
    )
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error("--seconds must be 1..60")
    logging.basicConfig(level=logging.INFO)
    with LeonidaAudio() as source:
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            if source.error:
                raise RuntimeError(source.error)
            try:
                source.packets.get(timeout=0.1)
            except queue.Empty:
                pass
        print(f"Leonida audio: frames={source.frames} peak={source.peak:.4f}; no recordings saved")
