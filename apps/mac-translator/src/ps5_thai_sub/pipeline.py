import re
import time

import numpy as np


class Stabilizer:
    """Only final utterances; suppress adjacent repeats for a short bounded interval."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.previous = ""
        self.last = float("-inf")

    def accept(self, text: str):
        normalized = re.sub(r"[\W_]+", "", text.casefold())
        now = self.clock()
        if not normalized or (normalized == self.previous and now - self.last < 8):
            return False
        self.previous, self.last = normalized, now
        return True


class Latencies:
    def __init__(self):
        self.values: list[float] = []

    def record(self, end: float):
        self.values.append(time.monotonic() - end)
        self.values = self.values[-1000:]

    def summary(self):
        if not self.values:
            return "No microphone latency samples"
        p50, p95 = np.percentile(self.values, [50, 95])
        return f"End-of-utterance → publish acknowledgement: n={len(self.values)} p50={p50:.2f}s p95={p95:.2f}s (not panel-render latency)"


def dialogue_only(text: str) -> str:
    """Drop explicit sound/lyric cues while retaining spoken words around cues."""
    if "♪" in text or "♫" in text:
        return ""
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>", "", text)
    if re.fullmatch(
        r"\s*(?:music|silence|applause|laughter|laughing|sighs?|gunshots?|explosion|background noise)[.! ]*",
        text,
        re.I,
    ):
        return ""
    return text.strip()
