"""App-filtered system audio from ScreenCaptureKit, no microphone or recording files."""

import hashlib
import json
import logging
import platform
import queue
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import webrtcvad

from .audio import Segmenter, Utterance

LOG = logging.getLogger("ps5-thai-sub")
DEFAULT_APP = "com.playstation.RemotePlay"


def build_helper() -> Path:
    if platform.system() != "Darwin" or int(platform.mac_ver()[0].split(".")[0]) < 14:
        raise RuntimeError("App audio capture requires macOS 14+ and Xcode Command Line Tools")
    source = Path(__file__).with_name("native") / "audio.swift"
    cache = Path.home() / "Library/Caches/ps5-thai-sub"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / ("audio-" + hashlib.sha256(source.read_bytes()).hexdigest()[:16])
    if not binary.exists():
        LOG.info("Building native app audio helper (first run)")
        try:
            result = subprocess.run(
                [
                    "xcrun",
                    "swiftc",
                    "-parse-as-library",
                    "-O",
                    str(source),
                    "-o",
                    str(binary),
                    "-framework",
                    "AppKit",
                    "-framework",
                    "ScreenCaptureKit",
                    "-framework",
                    "AVFoundation",
                    "-framework",
                    "CoreMedia",
                    "-framework",
                    "CoreImage",
                    "-framework",
                    "Vision",
                ],
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError(
                "Install Xcode Command Line Tools with xcode-select --install"
            ) from None
        if result.returncode:
            raise RuntimeError("App audio helper compilation failed; check Xcode/macOS SDK")
    return binary


class PCMFramer:
    """Reassemble arbitrary pipe reads into 20ms/320-sample frames."""

    def __init__(self):
        self.pending = bytearray()

    def feed(self, data: bytes):
        self.pending.extend(data)
        while len(self.pending) >= 1280:
            frame = np.frombuffer(bytes(self.pending[:1280]), dtype="<f4").copy()
            del self.pending[:1280]
            if not np.all(np.isfinite(frame)):
                raise ValueError("Non-finite audio samples")
            yield np.clip(frame, -1, 1)


class SpeechDetector:
    """Strict WebRTC speech gate; not source separation or a singing detector."""

    def __init__(self):
        self.vad = webrtcvad.Vad(3)

    def __call__(self, frame):
        pcm = (np.clip(frame, -1, 1) * 32767).astype("<i2").tobytes()
        return self.vad.is_speech(pcm, 16000)


class RemotePlayAudio:
    def __init__(
        self,
        app=DEFAULT_APP,
        threshold=0.006,
        binary=None,
        speech_detector=None,
        window_id=None,
        crops=None,
    ):
        self.binary = Path(binary) if binary else build_helper()
        self.app = app
        self.window_id = window_id
        self.crops = crops
        self.ocr_snapshot: tuple[float, list[str]] = (0.0, [])
        self.pending: queue.Queue[Utterance] = queue.Queue(maxsize=1)
        self.segmenter = Segmenter(
            threshold, speech_detector if speech_detector is not None else SpeechDetector()
        )
        self.segmenter.max_frames = 100  # Bound collection to 2s before ASR.
        self.segmenter.silence_frames = 15  # Finalize after 300ms without speech.
        self.framer = PCMFramer()
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.error: str | None = None
        self.dropped = 0
        self.frames = 0
        self.voiced_frames = 0
        self.peak = 0.0
        self.latest_rms = 0.0
        self.started = time.monotonic()
        self.last_report = self.started
        self.process = None
        self.threads: list[threading.Thread] = []

    def ingest(self, data: bytes):
        for frame in self.framer.feed(data):
            self.frames += 1
            self.latest_rms = float(np.sqrt(np.mean(frame * frame)))
            self.peak = max(self.peak, float(np.max(np.abs(frame))))
            if self.latest_rms >= self.segmenter.threshold:
                self.voiced_frames += 1
            utterance = self.segmenter.feed(frame, time.monotonic())
            if utterance:
                try:
                    self.pending.put_nowait(utterance)
                except queue.Full:
                    try:
                        self.pending.get_nowait()
                    except queue.Empty:
                        pass
                    self.pending.put_nowait(utterance)
                    self.dropped += 1

    def _audio(self):
        assert self.process is not None and self.process.stdout is not None
        try:
            while not self.closed.is_set():
                data = self.process.stdout.read(1280)
                if not data:
                    break
                self.ingest(data)
        except (OSError, ValueError):
            self.error = "Invalid or interrupted app audio stream"
        finally:
            if not self.closed.is_set():
                self.error = self.error or "App audio capture ended; reconnect Remote Play"
                self.ready.set()

    def _events(self):
        assert self.process is not None and self.process.stderr is not None
        for raw in self.process.stderr:
            if self.closed.is_set():
                return
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError):
                continue  # Ignore native framework diagnostics; never echo arbitrary stderr.
            if message.get("type") == "ocr":
                texts = message.get("texts")
                if (
                    isinstance(texts, list)
                    and self.crops
                    and len(texts) == len(self.crops)
                    and all(isinstance(t, str) and len(t) <= 2000 for t in texts)
                ):
                    self.ocr_snapshot = (time.monotonic(), texts)
                continue
            if message.get("type") == "ready":
                self.ready.set()
            elif message.get("type") == "error":
                self.error = message.get("message", "App audio capture failed")
                self.ready.set()

    def __enter__(self):
        command = [str(self.binary), self.app]
        if self.window_id is not None:
            command += [str(self.window_id), json.dumps(self.crops)]
        self.process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
        )
        self.threads = [
            threading.Thread(target=fn, daemon=True) for fn in (self._audio, self._events)
        ]
        try:
            for thread in self.threads:
                thread.start()
            if not self.ready.wait(15) or self.error:
                raise RuntimeError(
                    self.error or "App audio startup timed out; check capture permission"
                )
        except BaseException:
            self.close()
            raise
        LOG.info(
            "Remote Play audio active; strict speech filter enabled; microphone disabled; no recordings saved"
        )
        return self

    def next(self):
        if self.error:
            raise RuntimeError(self.error)
        if time.monotonic() - self.last_report >= 10:
            LOG.info(
                "App audio: frames=%d above_threshold=%d peak=%.3f dropped=%d",
                self.frames,
                self.voiced_frames,
                self.peak,
                self.dropped,
            )
            if not self.voiced_frames:
                LOG.warning(
                    "No audible app signal yet; check Remote Play audio volume/mute and PS5 connection"
                )
            self.last_report = time.monotonic()
        try:
            return self.pending.get(timeout=0.5)
        except queue.Empty:
            return None

    def close(self):
        self.closed.set()
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            for thread in self.threads:
                if thread.ident is not None:
                    thread.join(timeout=2)
            self.process.stdout.close()
            self.process.stderr.close()

    def __exit__(self, *args):
        self.close()
