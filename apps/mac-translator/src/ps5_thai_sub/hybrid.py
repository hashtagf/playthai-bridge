"""Single-capture hybrid with bounded jobs and a single owner of TV output."""

import logging
import queue
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher

from .ocr import OCRGate, key
from .pipeline import dialogue_only

LOG = logging.getLogger("ps5-thai-sub")


def similar(a, b):
    def normalized(text):
        return re.sub(r"[\W_]+", "", text.casefold())

    a, b = normalized(a), normalized(b)
    return bool(a and b) and (
        a == b or (min(len(a), len(b)) >= 12 and SequenceMatcher(None, a, b).ratio() >= 0.88)
    )


@dataclass
class Slot:
    text: str = ""
    thai: str = ""
    generation: int = 0
    seen: float = 0.0
    retry: float = 0.0


class Arbiter:
    def __init__(self, names, stable_seconds=0.6):
        self.slots = {name: Slot() for name in names}
        self.gates = {name: OCRGate(stable_seconds) for name in names}
        self.audio_text = self.audio_thai = ""
        self.audio_until = 0.0
        self.block_until = 0.0
        self.recent: list[tuple[str, float]] = []

    def observe(self, texts, now):
        for name, raw in texts.items():
            if name == "phone" and not (len(key(raw)) >= 60 and len(raw.split()) >= 10):
                raw = ""
            raw = dialogue_only(raw)
            slot = self.slots[name]
            slot.seen = now
            # Immediately hide stale output and block audio while a new subtitle stabilizes.
            if key(raw) != key(slot.text):
                slot.text, slot.thai = raw, ""
                slot.generation += 1
            if raw and name in ("subtitle", "phone"):
                self.block_until = now + 0.8
                self.audio_text = self.audio_thai = ""
            self.gates[name].observe(raw, now)

    def expire(self, now):
        for slot in self.slots.values():
            if slot.text and now - slot.seen > 3:
                slot.text = slot.thai = ""
                slot.generation += 1

    def audio_allowed(self, now, ended_at=None):
        self.expire(now)
        return now >= self.block_until and (ended_at is None or ended_at >= self.block_until)

    def next_ocr(self, now):
        phone = self.slots.get("phone")
        names = ["phone"] if phone and phone.text else ["subtitle", "chat"]
        for name in names:
            slot = self.slots.get(name)
            if slot and slot.text and not slot.thai and now >= slot.retry:
                gate = self.gates[name]
                if gate.samples >= 2 and now - gate.since >= gate.stable_seconds:
                    return name, slot.generation, slot.text
        return None

    def accept_ocr(self, name, generation, text, thai, now):
        slot = self.slots[name]
        if slot.generation != generation or now - slot.seen > 3:
            return False
        slot.thai = thai
        if name in ("subtitle", "phone"):
            self.recent.append((text, now))
        self.recent = self.recent[-20:]
        return True

    def accept_audio(self, text, thai, ended_at, now):
        if not self.audio_allowed(now, ended_at) or now - ended_at > 5:
            return False
        if any(now - stamp < 8 and similar(text, old) for old, stamp in self.recent):
            return False
        self.audio_text, self.audio_thai, self.audio_until = text, thai, now + 4
        self.recent.append((text, now))
        self.recent = self.recent[-20:]
        return True

    def render(self, now):
        self.expire(now)
        phone = self.slots.get("phone")
        if phone and phone.text:
            parts = [phone.thai]
        else:
            sub = self.slots["subtitle"]
            dialogue = (
                sub.thai
                if sub.text
                else (self.audio_thai if now < self.audio_until and self.audio_allowed(now) else "")
            )
            parts = [dialogue]
            chat = self.slots.get("chat")
            if chat and not similar(chat.text, sub.text or self.audio_text):
                parts.append(chat.thai)
        text = "\n".join(dict.fromkeys(p for p in parts if p))
        return text.encode("utf-16-le")[:1000].decode("utf-16-le", errors="ignore")


def run_hybrid(capture, names, translators, asr, publish, stable_seconds=0.6):
    arbiter = Arbiter(names, stable_seconds)
    last_snapshot = 0.0
    last_publish = 0.0
    last_text = ""
    last_health = time.monotonic()
    ocr_job = audio_job = None
    ocr_task = None
    audio_end = 0.0
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hybrid")

    def translate_audio(utterance):
        text = dialogue_only(asr.transcribe(utterance.audio))
        return text, translators["audio"].translate(text) if text else ""

    LOG.info("Hybrid active: one capture, OCR priority, speech fallback, single TV publisher")
    try:
        while True:
            now = time.monotonic()
            if capture.error:
                raise RuntimeError(capture.error)
            stamp, texts = capture.ocr_snapshot
            if stamp > last_snapshot:
                arbiter.observe(dict(zip(names, texts)), stamp)
                last_snapshot = stamp
            arbiter.expire(now)
            if ocr_job and ocr_job.done():
                assert ocr_task is not None
                name, generation, text = ocr_task
                try:
                    thai = ocr_job.result()
                    if arbiter.accept_ocr(name, generation, text, thai, now):
                        LOG.info("Hybrid accepted OCR source=%s", name)
                except Exception:
                    arbiter.slots[name].retry = now + 2
                    LOG.warning("Hybrid OCR translation failed (details redacted)")
                ocr_job = ocr_task = None
            if audio_job and audio_job.done():
                try:
                    text, thai = audio_job.result()
                    if thai and arbiter.accept_audio(text, thai, audio_end, now):
                        LOG.info("Hybrid accepted speech latency=%.2fs", now - audio_end)
                except Exception:
                    LOG.warning("Hybrid speech request failed (details redacted)")
                audio_job = None
            if ocr_job is None:
                ocr_task = arbiter.next_ocr(now)
                if ocr_task:
                    name, _, text = ocr_task
                    ocr_job = pool.submit(translators[name].translate, text)
            # Always drain latest audio, including while OCR is visible. No delayed replay.
            try:
                utterance = capture.pending.get_nowait()
            except queue.Empty:
                utterance = None
            if (
                utterance is not None
                and audio_job is None
                and arbiter.audio_allowed(now, utterance.ended_at)
                and now - utterance.ended_at <= 2
            ):
                audio_end = utterance.ended_at
                audio_job = pool.submit(translate_audio, utterance)
            text = arbiter.render(now)
            if text != last_text or (text and now - last_publish >= 3):
                if publish(text):
                    LOG.info("Hybrid TV acknowledged changed=%s", text != last_text)
                    last_text, last_publish = text, now
            if now - last_health >= 10:
                LOG.info(
                    "Hybrid health: ocr_age=%.1fs audio_frames=%d ocr_busy=%s speech_busy=%s",
                    now - last_snapshot if last_snapshot else -1,
                    capture.frames,
                    ocr_job is not None,
                    audio_job is not None,
                )
                if not last_snapshot or now - last_snapshot > 3:
                    LOG.warning("Hybrid OCR unavailable; speech fallback remains active")
                last_health = now
            time.sleep(0.1)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
