import base64

import httpx
import numpy as np
import pytest

from ps5_thai_sub.audio_relay import AudioRelay, LeonidaAudio, payload


def test_preserves_waveform_without_vad_and_bounds_queue():
    audio = LeonidaAudio(binary="/unused")
    samples = np.linspace(-1, 1, 1600, dtype="<f4")
    data = samples.tobytes()
    for _ in range(4):
        for i in range(0, len(data), 37):
            audio.ingest(data[i : i + 37])
    assert audio.packets.qsize() == 2
    assert audio.dropped == 2
    _, pcm = audio.packets.get_nowait()
    np.testing.assert_array_equal(np.frombuffer(pcm, dtype="<i2"), (samples * 32767).astype("<i2"))
    assert audio.frames == 20
    assert audio.peak == 1


def test_wire_payload_and_exact_packet_size():
    pcm = b"\x01\x00" * 1600
    data = payload("chunk", "session", 1, pcm)
    assert base64.b64decode(data["pcm"]) == pcm
    assert data["sample_rate"] == 16000 and data["format"] == "s16le"
    with pytest.raises(ValueError):
        payload("chunk", "s", 1, b"wrong")


def test_audio_transport_never_retries_chunk_and_checks_auth():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    relay = AudioRelay("127.0.0.1", "a" * 24, capture=LeonidaAudio(binary="/unused"))
    relay.client.close()
    relay.client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer " + "a" * 24}
    )
    with pytest.raises(httpx.HTTPStatusError):
        relay.send("chunk", "session", 1, bytes(3200))
    assert len(calls) == 1
    assert calls[0].headers["Authorization"] == "Bearer " + "a" * 24
    relay.client.close()


def test_source_closed_stops_relay_without_system_audio_fallback():
    capture = LeonidaAudio(binary="/unused")
    capture.error = "Source closed"
    relay = AudioRelay("127.0.0.1", "a" * 24, capture=capture)
    relay._run()
    assert relay.error == "Source closed"
    assert capture.app == "th.leonidasub.app"
    relay.client.close()
