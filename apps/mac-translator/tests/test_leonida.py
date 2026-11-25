import json

import pytest

from ps5_thai_sub.leonida import LiveTail, sse_events


def event(items, start=0, epoch=1):
    return {
        "log": {
            "epoch": epoch,
            "from": start,
            "n": start + len(items),
            "items": [{"th": t} for t in items],
        }
    }


def test_initial_history_not_replayed_then_only_newest():
    tail = LiveTail()
    assert tail.observe(event(["เก่า"])) is None
    assert tail.observe(event(["ใหม่", "ล่าสุด"], start=1)) == "ล่าสุด"
    assert tail.observe(event(["เก่า", "ใหม่", "ล่าสุด"])) is None


def test_reset_reconnect_and_duplicate_are_not_replayed():
    tail = LiveTail()
    tail.observe(event([]))
    assert tail.observe(event(["สวัสดี"])) == "สวัสดี"
    assert tail.observe(event(["สวัสดี"], start=1)) is None
    assert tail.observe(event(["อีกเซสชัน"], epoch=2)) is None
    assert LiveTail().observe(event(["เก่า", "ล่าสุด"])) is None


def test_bound_and_validation():
    tail = LiveTail()
    tail.observe(event([]))
    out = tail.observe(event(["ก" * 600 + "\x00"]))
    assert len(out.encode("utf-16-le")) <= 1000
    assert "\x00" not in out
    with pytest.raises(ValueError):
        tail.observe({"log": {"items": [], "from": 0, "n": 10}})


def test_sse_comments_multiline_and_multiple_events():
    payload = json.dumps(event([]))
    lines = [": heartbeat", "data: " + payload, "", "data: {}", "", ": keepalive", ""]
    assert list(sse_events(lines)) == [event([]), {}]
    with pytest.raises(ValueError):
        list(sse_events(["data: " + "x" * 200001]))
