import argparse
import logging
import os
import time

import httpx

from .audio import Microphone
from .models import PRESETS, resolve_model
from .ocr import WindowOCR, region, run_ocr
from .pipeline import Latencies, Stabilizer
from .protocol import Caption
from .providers import SAMPLES, APITranslator, MockTranslator, WhisperServer
from .publisher import Publisher
from .viewer import Preview

LOG = logging.getLogger("ps5-thai-sub")


def send_main():
    parser = argparse.ArgumentParser(description="Send a Thai caption; empty text hides it")
    parser.add_argument("--tv-host", required=True)
    parser.add_argument("--token", default=os.getenv("PS5_TV_TOKEN", ""))
    parser.add_argument("--text", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    publisher = None
    try:
        publisher = Publisher(args.tv_host, args.token, args.port)
        publisher.send(Caption.new(args.text))
        print("Caption acknowledged")
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    finally:
        if publisher:
            publisher.close()


def main():
    parser = argparse.ArgumentParser(description="Mac microphone → Thai subtitle overlay")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices", help="List microphone devices; no recording")
    sub.add_parser("models", help="Show model presets and effective default")
    sub.add_parser("ocr-windows", help="List visible window IDs for OCR selection")
    sub.add_parser("ocr-permission", help="Request macOS Screen Recording permission")
    sub.add_parser("ocr-self-test", help="Recognize a synthetic English subtitle without capture")
    run = sub.add_parser("run")
    run.add_argument("--input", choices=["microphone", "remote-play-ocr"], default="microphone")
    run.add_argument("--demo", action="store_true")
    run.add_argument("--window-id", type=int, help="Explicit capture window ID from ocr-windows")
    run.add_argument(
        "--ocr-region",
        default="0.10,0.65,0.80,0.28",
        help="x,y,width,height normalized from window top-left",
    )
    run.add_argument("--ocr-interval", type=float, default=0.3)
    run.add_argument("--ocr-stable-seconds", type=float, default=0.6)
    run.add_argument("--target", help="Literal private IPv4; omit for Mac-only fallback")
    run.add_argument("--token", default=os.getenv("PS5_TV_TOKEN", ""))
    run.add_argument("--port", type=int, default=8765)
    run.add_argument("--preview-port", type=int, default=8766)
    run.add_argument("--transcriber", choices=["whisper-server"], default="whisper-server")
    run.add_argument("--translator", choices=["openai-compatible"], default="openai-compatible")
    run.add_argument("--device", type=int)
    run.add_argument("--vad-threshold", type=float, default=0.015)
    run.add_argument("--demo-once", action="store_true", help="Exit after three fixture captions")
    run.add_argument(
        "--whisper-url", default=os.getenv("WHISPER_SERVER_URL", "http://127.0.0.1:18080")
    )
    run.add_argument(
        "--translation-url", default=os.getenv("TRANSLATION_BASE_URL", "http://127.0.0.1:11434/v1")
    )
    run.add_argument(
        "--model",
        help="openthai (default), gemma, or a full provider model ID; overrides TRANSLATION_MODEL",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    preview = publisher = asr = translator = None
    latency = Latencies()
    try:
        if args.command == "models":
            for alias, model in PRESETS.items():
                print(f"{alias}: {model}")
            print(f"Effective default: {resolve_model()}")
            return
        if args.command.startswith("ocr-"):
            source = WindowOCR()
            if args.command == "ocr-windows":
                for window in source.windows():
                    print(f"{window['id']} | {window['app']} | {window['title']}")
            elif args.command == "ocr-permission":
                granted = source.command("--permission")["granted"]
                print(
                    "Screen Recording allowed"
                    if granted
                    else "Allow Screen Recording in macOS Settings, then restart the launching app"
                )
            else:
                print(source.command("--self-test")["text"])
            return
        if args.command == "devices":
            import sounddevice as sd

            print(sd.query_devices())
            return
        args.model = resolve_model(args.model)
        if not args.demo:
            LOG.info("Translation model: %s", args.model)
        if args.demo_once and not args.demo:
            raise ValueError("--demo-once requires --demo")
        if not 0 < args.vad_threshold < 1:
            raise ValueError("VAD threshold must be between zero and one")
        crop = region(args.ocr_region)
        if not 0.1 <= args.ocr_interval <= 5 or not 0.2 <= args.ocr_stable_seconds <= 5:
            raise ValueError("OCR interval must be 0.1..5s and stability 0.2..5s")
        publisher = Publisher(args.target, args.token, args.port) if args.target else None
        preview = Preview(args.preview_port)
        LOG.info("Mac viewer: http://127.0.0.1:%d", preview.port)

        def publish(text):
            caption = Caption.new(text)
            preview.send(caption)
            if publisher:
                try:
                    publisher.send(caption)
                except RuntimeError as error:
                    LOG.warning("%s; Mac preview remains available", error)
                    return False
            return True

        if args.demo:
            LOG.info("DEMO: deterministic fixtures, no microphone, AI model or API calls")
            mock = MockTranslator()
            while True:
                for phrase in SAMPLES:
                    thai = mock.translate(phrase)
                    publish(thai)
                    print(thai, flush=True)  # Canned fixture only, never live dialogue.
                    time.sleep(3)
                if args.demo_once:
                    break
        elif args.input == "remote-play-ocr":
            source = WindowOCR()
            window_id = source.select(args.window_id)
            translator = APITranslator(
                args.translation_url, args.model, os.getenv("TRANSLATION_API_KEY", "")
            )
            translator.check()
            # Read once before starting to fail clearly on permission/capture errors.
            source.read(window_id, crop)
            run_ocr(
                source,
                window_id,
                crop,
                translator,
                publish,
                args.ocr_interval,
                args.ocr_stable_seconds,
            )
        else:
            asr = WhisperServer(args.whisper_url)
            translator = APITranslator(
                args.translation_url, args.model, os.getenv("TRANSLATION_API_KEY", "")
            )
            asr.check()
            translator.check()
            stable = Stabilizer()
            with Microphone(args.device, args.vad_threshold) as mic:
                LOG.info("Microphone active; no recordings saved. Ctrl-C stops capture.")
                while True:
                    utterance = mic.next()
                    if utterance is None:
                        continue
                    if time.monotonic() - utterance.ended_at > 10:
                        continue  # Drop stale work, never replay a dialogue backlog.
                    try:
                        text = asr.transcribe(utterance.audio)
                        if not stable.accept(text):
                            continue
                        thai = translator.translate(text)
                        if time.monotonic() - utterance.ended_at > 15:
                            LOG.warning("Dropped stale translation")
                            continue
                        if publish(thai):
                            latency.record(utterance.ended_at)
                            LOG.info(latency.summary())
                    except (httpx.HTTPError, ValueError, KeyError, IndexError):
                        LOG.warning(
                            "Speech/translation request failed; skipped utterance (details redacted)"
                        )
    except KeyboardInterrupt:
        LOG.info("Stopped")
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Startup failed: {error}\n")
    finally:
        if publisher:
            try:
                publisher.send(Caption.new(""))
            except RuntimeError:
                pass
        for resource in (preview, publisher, asr, translator):
            if resource:
                resource.close()
        if latency.values:
            LOG.info(latency.summary())


if __name__ == "__main__":
    main()
