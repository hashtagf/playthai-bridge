"""Energy VAD and bounded capture. No audio files and no unbounded backlog."""

import queue
import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class Utterance:
    audio: np.ndarray
    ended_at: float


class Segmenter:
    def __init__(self, threshold=0.015):
        self.threshold = threshold
        self.pre: deque[np.ndarray] = deque(maxlen=5)
        self.frames: list[np.ndarray] = []
        self.silent = 0
        self.voiced = 0
        self.last_voice = 0.0

    def feed(self, frame: np.ndarray, now: float) -> Utterance | None:
        # 20ms mono float32 blocks. Remove DC before RMS, not a learned denoiser.
        signal = frame - frame.mean()
        active = float(np.sqrt(np.mean(signal * signal))) >= self.threshold
        if not self.frames and not active:
            self.pre.append(frame.copy())
            return None
        if not self.frames:
            self.frames.extend(self.pre)
            self.pre.clear()
        self.frames.append(frame.copy())
        if active:
            self.last_voice = now
            self.silent = 0
            self.voiced += 1
        else:
            self.silent += 1
        if self.silent >= 25 or len(self.frames) >= 400:
            result = (
                Utterance(np.concatenate(self.frames), self.last_voice)
                if self.voiced >= 10
                else None
            )
            self.frames = []
            self.silent = self.voiced = 0
            return result
        return None


class Microphone:
    def __init__(self, device=None, threshold=0.015):
        import sounddevice as sd

        self.sd = sd
        try:
            sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=16000)
        except (sd.PortAudioError, ValueError):
            raise RuntimeError(
                "No usable 16kHz microphone. Check --device and macOS Microphone permission"
            ) from None
        self.pending: queue.Queue[Utterance] = queue.Queue(maxsize=1)
        self.segmenter = Segmenter(threshold)
        self.dropped = 0

        def callback(data, frames, timing, status):
            if status:
                self.dropped += 1
            utterance = self.segmenter.feed(data[:, 0], time.monotonic())
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

        self.stream = sd.InputStream(
            device=device,
            channels=1,
            samplerate=16000,
            blocksize=320,
            dtype="float32",
            callback=callback,
        )

    def __enter__(self):
        try:
            self.stream.start()
        except self.sd.PortAudioError:
            self.stream.close()
            raise RuntimeError(
                "Microphone start failed; allow the terminal in macOS Privacy & Security → Microphone"
            ) from None
        return self

    def __exit__(self, *args):
        self.stream.stop()
        self.stream.close()

    def next(self):
        try:
            return self.pending.get(timeout=0.5)
        except queue.Empty:
            return None
