import httpx
import numpy as np
import pytest
from ps5_thai_sub.audio import Segmenter
from ps5_thai_sub.pipeline import Stabilizer
from ps5_thai_sub.protocol import Caption
from ps5_thai_sub.providers import SAMPLES, APITranslator, MockTranslator
from ps5_thai_sub.publisher import Publisher, lan_host
from ps5_thai_sub.viewer import Preview


def test_demo_reference_translations():
    for english, thai in SAMPLES.items():
        assert MockTranslator().translate(english) == thai


def test_utf8_and_validation():
    c = Caption.new(SAMPLES[next(iter(SAMPLES))])
    assert c.payload()["language"] == "th"
    assert Caption(**c.payload()) == c
    for text in ("x" * 501, "bad\x00"):
        with pytest.raises(ValueError):
            Caption.new(text)
    with pytest.raises(ValueError):
        Caption.new("test", 0)


@pytest.mark.parametrize(
    "host", ["8.8.8.8", "169.254.1.1", "example.com", "127.0.0.1:80", "0.0.0.0"]
)
def test_reject_non_lan_target(host):
    with pytest.raises(ValueError):
        lan_host(host)


def test_auth_failure_no_retry():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(401)

    p = Publisher("127.0.0.1", "x" * 24, client=httpx.Client(transport=httpx.MockTransport(handle)))
    with pytest.raises(RuntimeError, match="pairing"):
        p.send(Caption.new("ไทย"))
    assert len(calls) == 1
    p.close()


def test_lost_connection_bounded_retry_same_id():
    calls, sleeps = [], []

    def handle(request):
        calls.append(request.content)
        raise httpx.ConnectError("unavailable")

    p = Publisher(
        "127.0.0.1",
        "x" * 24,
        sleep=sleeps.append,
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(RuntimeError, match="three"):
        p.send(Caption.new("ไทย"))
    assert len(calls) == 3 and len(set(calls)) == 1
    assert sleeps == [0.15, 0.3]
    p.close()


def test_retry_then_success():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 202)

    p = Publisher(
        "127.0.0.1",
        "x" * 24,
        sleep=lambda _: None,
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    p.send(Caption.new("ไทย"))
    assert len(calls) == 2
    p.close()


def test_expiry_replacement_and_browser_security():
    now = [10.0]
    preview = Preview(port=0, clock=lambda: now[0])
    try:
        preview.send(Caption.new("ไทย", 1000))
        url = f"http://127.0.0.1:{preview.port}"
        with httpx.Client(trust_env=False) as client:
            assert client.get(url + "/caption").json()["text"] == "ไทย"
            assert client.get(url, headers={"Host": "evil.example"}).status_code == 403
            assert "textContent" in client.get(url).text
            now[0] += 1
            assert client.get(url + "/caption").json()["text"] == ""
        preview.send(Caption.new("replacement"))
        preview.send(Caption.new(""))
        assert preview.current() == ""
    finally:
        preview.close()


def test_stabilizer_and_repeated_real_dialogue():
    now = [0.0]
    stable = Stabilizer(clock=lambda: now[0])
    assert stable.accept("Go!")
    assert not stable.accept("go")
    assert not stable.accept(" ")
    now[0] = 9
    assert stable.accept("Go!")


def test_vad_silence_speech_and_end_timestamp():
    vad = Segmenter()
    silence = np.zeros(320, dtype=np.float32)
    speech = np.sin(np.arange(320) * 0.1).astype(np.float32) * 0.1
    for i in range(100):
        assert vad.feed(silence, i * 0.02) is None
    for i in range(20):
        assert vad.feed(speech, 2 + i * 0.02) is None
    result = None
    for i in range(25):
        result = vad.feed(silence, 2.4 + i * 0.02)
    assert result is not None
    assert result.ended_at == pytest.approx(2.38)
    assert len(result.audio) <= 400 * 320


def test_vad_max_chunk_and_short_noise():
    vad = Segmenter()
    speech = np.sin(np.arange(320) * 0.1).astype(np.float32) * 0.1
    completed = [vad.feed(speech, i * 0.02) for i in range(400)]
    assert completed[-1] is not None
    assert len(completed[-1].audio) == 400 * 320


def test_translation_request_context_and_invalid_output():
    requests = []

    def handle(request):
        requests.append(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "อยู่ใกล้ฉันไว้" if len(requests) == 1 else "ประตูถูกล็อกอยู่"}}
                ]
            },
        )

    t = APITranslator(
        "http://127.0.0.1/v1",
        "test",
        client=httpx.Client(base_url="http://127.0.0.1/v1/", transport=httpx.MockTransport(handle)),
    )
    assert t.translate("Stay close to me.") == "อยู่ใกล้ฉันไว้"
    t.translate("The gate is locked.")
    assert requests[-1]["messages"][-1]["content"] == "The gate is locked."
    assert requests[-1]["messages"][1]["content"] == "Stay close to me."
    t.close()


def test_lost_connection_mid_response_retries():
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.RemoteProtocolError("peer closed")

    p = Publisher(
        "127.0.0.1",
        "x" * 24,
        sleep=lambda _: None,
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(RuntimeError, match="three"):
        p.send(Caption.new("ไทย"))
    assert len(calls) == 3
    p.close()


def test_asr_in_memory_wav_contract():
    from ps5_thai_sub.providers import WhisperServer

    captured = []

    def handle(request):
        captured.append(request)
        return httpx.Response(200, json={"text": " We have to leave before dawn. "})

    asr = WhisperServer("http://127.0.0.1:8080")
    asr.client.close()
    asr.client = httpx.Client(
        base_url="http://127.0.0.1:8080", transport=httpx.MockTransport(handle)
    )
    assert asr.transcribe(np.zeros(16000, dtype=np.float32)) == "We have to leave before dawn."
    assert captured[0].url.path == "/inference"
    assert b"RIFF" in captured[0].content and b"WAVE" in captured[0].content
    assert b'name="language"' in captured[0].content
    asr.close()


def test_translation_rejects_empty_non_thai_or_unbounded():
    for output in ["", "invented English only", "ก" * 501]:
        client = httpx.Client(
            base_url="http://127.0.0.1/v1/",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": output}}]}
                )
            ),
        )
        t = APITranslator("http://127.0.0.1/v1", "test", client=client)
        with pytest.raises(ValueError):
            t.translate("Hello")
        t.close()


def test_short_noise_does_not_create_utterance():
    vad = Segmenter()
    speech = np.sin(np.arange(320) * 0.1).astype(np.float32) * 0.1
    for i in range(3):
        assert vad.feed(speech, i * 0.02) is None
    for i in range(30):
        assert vad.feed(np.zeros(320, dtype=np.float32), 1 + i * 0.02) is None


def test_microphone_backpressure_keeps_latest(monkeypatch):
    import sys
    from types import SimpleNamespace

    from ps5_thai_sub.audio import Microphone, Utterance

    callbacks = []

    class FakeStream:
        def __init__(self, **kwargs):
            callbacks.append(kwargs["callback"])

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(check_input_settings=lambda **kw: None, InputStream=FakeStream),
    )
    microphone = Microphone()
    utterances = iter(Utterance(np.zeros(320), float(i)) for i in range(3))
    microphone.segmenter.feed = lambda *args: next(utterances)
    for _ in range(3):
        callbacks[0](np.zeros((320, 1)), 320, None, None)
    assert microphone.pending.qsize() == 1
    assert microphone.next().ended_at == 2
    assert microphone.dropped == 2


def test_context_echo_rejected():
    client = httpx.Client(
        base_url="http://127.0.0.1/v1/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "อยู่ใกล้ฉันไว้"}}]}
            )
        ),
    )
    t = APITranslator("http://127.0.0.1/v1", "test", client=client)
    t.translate("Stay close to me.")
    with pytest.raises(ValueError, match="echoed"):
        t.translate("The gate is locked.")
    assert len(t.context) == 1
    t.close()
