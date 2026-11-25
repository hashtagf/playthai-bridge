"""Optional real-model smoke using synthetic speech, never microphone recordings.
Needs macOS say, running whisper-server and Ollama model. Run from repository root.
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
from ps5_thai_sub.protocol import Caption
from ps5_thai_sub.providers import SAMPLES, APITranslator, WhisperServer
from ps5_thai_sub.publisher import Publisher

parser = argparse.ArgumentParser()
parser.add_argument("--whisper-url", default="http://127.0.0.1:18080")
parser.add_argument("--model", default="gemma3:4b")
parser.add_argument("--tv-host")
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
asr = WhisperServer(args.whisper_url)
translator = APITranslator("http://127.0.0.1:11434/v1", args.model)
publisher = (
    Publisher(args.tv_host, os.environ.get("PS5_TV_TOKEN", ""), args.port) if args.tv_host else None
)
results = []
try:
    asr.check()
    translator.check()
    with tempfile.TemporaryDirectory(prefix="ps5-synthetic-") as directory:
        for english, reference in SAMPLES.items():
            filename = str(Path(directory) / "synthetic.wav")
            subprocess.run(
                [
                    "say",
                    "-v",
                    "Samantha",
                    "-o",
                    filename,
                    "--file-format=WAVE",
                    "--data-format=LEI16@16000",
                    english,
                ],
                check=True,
            )
            with wave.open(filename) as wav:
                audio = (
                    np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32)
                    / 32768
                )
            start = time.monotonic()
            recognized = asr.transcribe(audio)
            thai = translator.translate(recognized)
            if publisher:
                publisher.send(Caption.new(thai))
            results.append(
                {
                    "fixture": english,
                    "asr": recognized,
                    "reference": reference,
                    "model_output": thai,
                    "processing_seconds": time.monotonic() - start,
                }
            )
    times = [item["processing_seconds"] for item in results]
    output = {
        "kind": "synthetic WAV → real ASR → real translation → optional publish acknowledgement",
        "model": args.model,
        "tv_published": publisher is not None,
        "not_measured": "actual microphone EOU, VAD wait, physical panel latency or human-rated quality",
        "samples": results,
        "n": len(times),
        "p50_seconds": float(np.percentile(times, 50)),
        "p95_seconds": float(np.percentile(times, 95)),
    }
    Path("docs/evidence").mkdir(parents=True, exist_ok=True)
    Path("docs/evidence/ai-smoke.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
finally:
    if publisher:
        publisher.close()
    asr.close()
    translator.close()
