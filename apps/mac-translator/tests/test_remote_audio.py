import io
import json

import numpy as np
import pytest

from ps5_thai_sub.remote_audio import PCMFramer, RemotePlayAudio


def test_pcm_split_reads_preserve_exact_samples():
    data = np.linspace(-0.5, 0.5, 640, dtype="<f4")
    raw = data.tobytes()
    framer = PCMFramer()
    output = []
    for start in range(0, len(raw), 73):
        output.extend(framer.feed(raw[start : start + 73]))
    assert len(output) == 2
    np.testing.assert_array_equal(np.concatenate(output), data)
    assert len(framer.pending) == 0


def test_partial_frame_is_retained_and_nan_rejected():
    framer = PCMFramer()
    assert list(framer.feed(b"\0" * 100)) == []
    assert len(framer.pending) == 100
    assert len(list(framer.feed(b"\0" * 1180))) == 1
    with pytest.raises(ValueError, match="Non-finite"):
        list(framer.feed(np.full(320, np.nan, dtype="<f4").tobytes()))


def test_silence_and_bounded_latest_utterance():
    source = RemotePlayAudio(binary="/unused")
    silence = np.zeros(320, dtype="<f4").tobytes()
    for _ in range(30):
        source.ingest(silence)
    assert source.pending.empty() and source.voiced_frames == 0
    speech = (np.sin(np.arange(320) * 0.1) * 0.1).astype("<f4").tobytes()
    for _ in range(3):
        for _ in range(20):
            source.ingest(speech)
        for _ in range(25):
            source.ingest(silence)
    assert source.pending.qsize() == 1
    assert source.dropped == 2
    assert source.frames == 165
    assert source.peak > 0.09
    assert source.next().audio.size > 0


def test_audio_continuous_music_chunks_bounded_to_four_seconds():
    source = RemotePlayAudio(binary="/unused")
    speech = (np.sin(np.arange(320) * 0.1) * 0.1).astype("<f4").tobytes()
    for _ in range(200):
        source.ingest(speech)
    assert source.next().audio.size == 16000 * 4


def test_native_error_report_is_actionable_and_process_cleaned(monkeypatch):
    class FailedProcess:
        def __init__(self, *args, **kwargs):
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO(
                (json.dumps({"type": "error", "message": "Permission required"}) + "\n").encode()
            )

        def poll(self):
            return 3

    monkeypatch.setattr("ps5_thai_sub.remote_audio.subprocess.Popen", FailedProcess)
    source = RemotePlayAudio(binary="/unused")
    with pytest.raises(RuntimeError):
        with source:
            pass
    assert source.closed.is_set()
    assert all(not thread.is_alive() for thread in source.threads)


def test_native_protocol_ready_and_stream_error():
    source = RemotePlayAudio(binary="/unused")

    class Process:
        stderr = io.BytesIO(b'{"type":"ready"}\n{"type":"error","message":"source closed"}\n')

    source.process = Process()
    source._events()
    assert source.ready.is_set()
    with pytest.raises(RuntimeError, match="source closed"):
        source.next()


def test_audio_end_does_not_silently_wait_forever():
    source = RemotePlayAudio(binary="/unused")

    class Process:
        stdout = io.BytesIO()

    source.process = Process()
    source._audio()
    with pytest.raises(RuntimeError, match="ended"):
        source.next()
