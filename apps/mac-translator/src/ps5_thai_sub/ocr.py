"""macOS window-only OCR. Images remain in native process memory."""

import hashlib
import json
import logging
import platform
import re
import subprocess
import time
from pathlib import Path

import httpx

LOG = logging.getLogger("ps5-thai-sub")


def region(value: str) -> tuple[float, float, float, float]:
    try:
        x, y, w, h = map(float, value.split(","))
    except ValueError:
        raise ValueError("OCR region must be x,y,width,height fractions") from None
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x and 0 < h <= 1 - y):
        raise ValueError("OCR region must fit inside the window (values 0..1)")
    return x, y, w, h


def key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class OCRGate:
    def __init__(self, stable_seconds=0.6):
        self.stable_seconds = stable_seconds
        self.candidate = ""
        self.since = 0.0
        self.samples = 0

    def observe(self, text: str, now: float) -> str | None:
        normalized = key(text)
        if normalized != self.candidate:
            self.candidate, self.since, self.samples = normalized, now, 1
            return None
        self.samples += 1
        if self.samples >= 2 and now - self.since >= self.stable_seconds:
            return re.sub(r"\s+", " ", text).strip()
        return None


class WindowOCR:
    def __init__(self):
        if platform.system() != "Darwin" or int(platform.mac_ver()[0].split(".")[0]) < 14:
            raise RuntimeError("Remote Play OCR requires macOS 14+ and Xcode Command Line Tools")
        source = Path(__file__).with_name("native") / "ocr.swift"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        cache = Path.home() / "Library/Caches/ps5-thai-sub"
        cache.mkdir(parents=True, exist_ok=True)
        self.binary = cache / f"ocr-{digest}"
        if not self.binary.exists():
            LOG.info("Building native Apple Vision helper (first run)")
            try:
                result = subprocess.run(
                    [
                        "xcrun",
                        "swiftc",
                        "-parse-as-library",
                        "-O",
                        str(source),
                        "-o",
                        str(self.binary),
                        "-framework",
                        "AppKit",
                        "-framework",
                        "Vision",
                        "-framework",
                        "ScreenCaptureKit",
                    ],
                    capture_output=True,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise RuntimeError(
                    "Install Xcode Command Line Tools with xcode-select --install"
                ) from None
            if result.returncode:
                raise RuntimeError(
                    "Native OCR build failed; check supported macOS SDK/Xcode installation"
                )

    def command(self, *args):
        try:
            result = subprocess.run(
                [str(self.binary), *map(str, args)], capture_output=True, text=True, timeout=15
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Window capture timed out; check Screen Recording permission"
            ) from None
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise RuntimeError("Native OCR returned invalid output; restart capture") from None
        if result.returncode:
            raise RuntimeError(data.get("error", "Window OCR failed"))
        return data

    def windows(self):
        return self.command("--list")

    def select(self, window_id=None):
        windows = self.windows()
        matches = (
            [w for w in windows if w["id"] == window_id]
            if window_id
            else [w for w in windows if "remoteplay" in w["app"].lower().replace(" ", "")]
        )
        if len(matches) != 1:
            raise RuntimeError(
                "Open PS Remote Play and connect PS5; use ocr-windows then --window-id if selection is ambiguous"
            )
        return matches[0]["id"]

    def read(self, window_id, crop):
        text = self.command(window_id, *crop)["text"]
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError("OCR output exceeded limit")
        return text


def run_ocr(source, window_id, crop, translator, publish, interval=0.3, stable_seconds=0.6):
    gate = OCRGate(stable_seconds)
    displayed = ""
    translation = ""
    last_publish = 0.0
    retry_after = 0.0
    count = 0
    LOG.info("Window OCR active; no microphone or image files. Ctrl-C stops.")
    while True:
        started = time.monotonic()
        text = source.read(window_id, crop)
        ready = gate.observe(text, started)
        if ready is not None:
            normalized = key(ready)
            if not ready:
                if displayed:
                    publish("")
                displayed = translation = ""
            elif normalized == displayed:
                # Renew while source remains visible; never retranslate unchanged subtitles.
                if started - last_publish >= 3:
                    publish(translation)
                    last_publish = started
            elif started >= retry_after:
                try:
                    result = translator.translate(ready)
                    # Translation may have taken seconds. Reject an obsolete line before publish.
                    current = source.read(window_id, crop)
                    if key(current) != normalized:
                        gate.observe(current, time.monotonic())
                        if displayed:
                            publish("")
                        displayed = translation = ""
                        continue
                    if publish(result):
                        displayed, translation = normalized, result
                        last_publish = time.monotonic()
                        count += 1
                        LOG.info(
                            "OCR caption acknowledged n=%d processing=%.2fs",
                            count,
                            last_publish - started,
                        )
                except (httpx.HTTPError, ValueError, KeyError, IndexError):
                    retry_after = time.monotonic() + 2
                    LOG.warning("OCR translation failed; retry delayed (content redacted)")
        time.sleep(max(0.01, interval - (time.monotonic() - started)))
