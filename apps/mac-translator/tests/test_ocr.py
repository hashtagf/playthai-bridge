import pytest

from ps5_thai_sub.ocr import OCRGate, key, region, run_ocr


def test_region_bounds():
    assert region(".1,.65,.8,.28") == (0.1, 0.65, 0.8, 0.28)
    for value in ("1,2,3", "0,0,2,1", "nan,0,1,1", "0,0,-1,1"):
        with pytest.raises(ValueError):
            region(value)


def test_stability_partial_updates_and_blank():
    gate = OCRGate(0.6)
    assert gate.observe("We have", 0) is None
    assert gate.observe("We have to leave.", 0.3) is None
    assert gate.observe("We have to leave.", 0.7) is None
    assert gate.observe("We have to leave.", 1) == "We have to leave."
    assert gate.observe("", 1.1) is None
    assert gate.observe("", 1.8) == ""
    assert key(" Hello  WORLD ") == "hello world"


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Source:
    def __init__(self, samples):
        self.samples = iter(samples)

    def read(self, *args):
        try:
            return next(self.samples)
        except StopIteration:
            raise KeyboardInterrupt from None


class Translator:
    def __init__(self):
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return "ประตูถูกล็อกอยู่"


def execute(monkeypatch, samples):
    clock = Clock()
    monkeypatch.setattr("ps5_thai_sub.ocr.time.monotonic", clock.monotonic)
    monkeypatch.setattr("ps5_thai_sub.ocr.time.sleep", clock.sleep)
    sent = []
    translator = Translator()

    def publish(text):
        sent.append(text)
        return True

    with pytest.raises(KeyboardInterrupt):
        run_ocr(Source(samples), 1, (0, 0, 1, 1), translator, publish, 0.5, 0.5)
    return sent, translator.calls


def test_unchanged_subtitle_not_retranslated_and_blank_hides(monkeypatch):
    sent, calls = execute(monkeypatch, ["The gate is locked."] * 12 + [""] * 3)
    assert calls == ["The gate is locked."]
    assert sent == ["ประตูถูกล็อกอยู่", "ประตูถูกล็อกอยู่", ""]


def test_changed_during_translation_never_published(monkeypatch):
    sent, calls = execute(monkeypatch, ["Old line", "Old line", "New line"])
    assert calls == ["Old line"]
    assert sent == []


def test_disappearance_during_translation_never_published(monkeypatch):
    sent, calls = execute(monkeypatch, ["Old line", "Old line", "", ""])
    assert sent == []


def test_same_line_can_reappear_after_blank(monkeypatch):
    sent, calls = execute(monkeypatch, ["Hello"] * 3 + [""] * 2 + ["Hello"] * 3)
    assert calls == ["Hello", "Hello"]
    assert sent == ["ประตูถูกล็อกอยู่", "", "ประตูถูกล็อกอยู่"]
