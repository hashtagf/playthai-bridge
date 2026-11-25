from ps5_thai_sub.hybrid import Arbiter, similar


def stabilize(a, texts, start=1):
    a.observe(texts, start)
    a.observe(texts, start + 1)


def test_ocr_blocks_pending_audio_and_late_completion():
    a = Arbiter(["subtitle"])
    assert a.audio_allowed(1)
    a.observe({"subtitle": "Stay close"}, 2)
    assert not a.audio_allowed(2)
    assert not a.accept_audio("Stay close", "อยู่ใกล้กัน", 1.5, 2.1)
    stabilize(a, {"subtitle": "Stay close"}, 2)
    name, gen, text = a.next_ocr(3)
    assert a.accept_ocr(name, gen, text, "อยู่ใกล้กัน", 3)
    assert a.render(3) == "อยู่ใกล้กัน"


def test_changed_or_expired_ocr_job_is_rejected():
    a = Arbiter(["subtitle"])
    stabilize(a, {"subtitle": "Old"})
    task = a.next_ocr(2)
    a.observe({"subtitle": "New"}, 2.1)
    assert not a.accept_ocr(*task, "เก่า", 2.2)
    stabilize(a, {"subtitle": "New"}, 3)
    task = a.next_ocr(4)
    assert not a.accept_ocr(*task, "ใหม่", 8)
    assert a.audio_allowed(8)
    assert a.render(8) == ""


def test_chat_coexists_with_audio_and_does_not_block_it():
    a = Arbiter(["subtitle", "chat"])
    stabilize(a, {"subtitle": "", "chat": "Text message"})
    assert a.audio_allowed(2)
    assert a.accept_ocr(*a.next_ocr(2), "ข้อความแชท", 2)
    assert a.accept_audio("Go away", "ออกไป", 2, 2.1)
    assert a.render(2.2) == "ออกไป\nข้อความแชท"


def test_duplicate_audio_after_ocr_and_old_audio_never_replayed():
    a = Arbiter(["subtitle"])
    stabilize(a, {"subtitle": "We have to leave now."})
    a.accept_ocr(*a.next_ocr(2), "เราต้องไปแล้ว", 2)
    a.observe({"subtitle": ""}, 3)
    assert not a.accept_audio("We have to leave now!", "เราต้องไปแล้ว", 4, 4.1)
    assert not a.accept_audio("Something new", "ใหม่", 1, 7)
    assert a.accept_audio("Different dialogue", "บทพูดใหม่", 4, 4.2)
    assert a.render(9) == ""


def test_phone_priority_then_audio_recovers():
    a = Arbiter(["subtitle", "phone"])
    phone = (
        "Thank you thank you. Money in your mailbox. You got my plane? You better be good to her!"
    )
    stabilize(a, {"subtitle": "Hello", "phone": phone})
    task = a.next_ocr(2)
    assert task[0] == "phone"
    a.accept_ocr(*task, "ข้อความมือถือ", 2)
    assert a.render(2) == "ข้อความมือถือ"
    a.observe({"subtitle": "", "phone": ""}, 3)
    assert a.audio_allowed(4)
    assert a.accept_audio("New speech", "พูดใหม่", 4, 4.1)
    assert a.render(4.1) == "พูดใหม่"


def test_duplicates_and_utf16_output_bound():
    assert similar("We should leave now!", "we should leave now.")
    assert not similar("Yes", "No")
    a = Arbiter(["subtitle", "chat"])
    stabilize(a, {"subtitle": "Hello", "chat": "Different"})
    a.slots["subtitle"].thai = "ก" * 400
    a.slots["chat"].thai = "ข" * 400
    assert len(a.render(2).encode("utf-16-le")) <= 1000


def test_runner_translates_audio_and_chat_with_single_publisher(monkeypatch):
    import queue
    from types import SimpleNamespace

    import numpy as np
    import pytest

    from ps5_thai_sub.audio import Utterance
    from ps5_thai_sub.hybrid import run_hybrid

    class Clock:
        now = 1.0

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += 0.5
            if self.now >= 4:
                raise KeyboardInterrupt
            capture.ocr_snapshot = (self.now, ["", "A chat message"])

    class Future:
        def __init__(self, fn, text):
            self.value = fn(text)

        def done(self):
            return True

        def result(self):
            return self.value

    class Pool:
        closed = False

        def __init__(self, **kwargs):
            pass

        def submit(self, fn, text):
            return Future(fn, text)

        def shutdown(self, **kwargs):
            Pool.closed = True

    class Translator:
        def translate(self, text):
            return "แชท" if text == "A chat message" else "เสียงพูด"

    clock = Clock()
    capture = SimpleNamespace(
        error=None, ocr_snapshot=(1.0, ["", "A chat message"]), pending=queue.Queue(), frames=100
    )
    capture.pending.put(Utterance(np.zeros(16000), 1.0))
    asr = SimpleNamespace(transcribe=lambda audio: "Go away")
    monkeypatch.setattr("ps5_thai_sub.hybrid.time.monotonic", clock.monotonic)
    monkeypatch.setattr("ps5_thai_sub.hybrid.time.sleep", clock.sleep)
    monkeypatch.setattr("ps5_thai_sub.hybrid.ThreadPoolExecutor", Pool)
    sent = []

    def publish(text):
        sent.append(text)
        return True

    with pytest.raises(KeyboardInterrupt):
        run_hybrid(
            capture,
            ["subtitle", "chat"],
            {name: Translator() for name in ["subtitle", "chat", "audio"]},
            asr,
            publish,
            0.3,
        )
    assert "เสียงพูด" in sent
    assert "เสียงพูด\nแชท" in sent
    assert Pool.closed
