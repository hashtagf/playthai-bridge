"""Run using uv run from Mac project. Requires installed debug APK + granted overlay permission.
Usage: uv run --project apps/mac-translator python scripts/emulator_smoke.py --serial emulator-5556
Never use on a physical TV: script changes foreground Activity, then stops the test app.
"""

import argparse
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from ps5_thai_sub.protocol import Caption

parser = argparse.ArgumentParser()
parser.add_argument("--serial", required=True)
args = parser.parse_args()
if not args.serial.startswith("emulator-"):
    parser.error("Emulator only; use the physical manual worksheet for TV")
adb = [
    str(
        Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
        / "platform-tools/adb"
    ),
    "-s",
    args.serial,
]
package = "dev.ps5thaisub.overlay"


def call(*args):
    return subprocess.check_output([*adb, *args])


def click(label):
    call("shell", "uiautomator", "dump", "/sdcard/ps5-smoke.xml")
    root = ET.fromstring(call("shell", "cat", "/sdcard/ps5-smoke.xml"))
    node = next(n for n in root.iter("node") if n.get("text") == label)
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.attrib["bounds"]))
    call("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def visible():
    return (
        f"package={package} appop=SYSTEM_ALERT_WINDOW"
        in call("shell", "dumpsys", "window", "windows").decode()
    )


def wait_visible(expected):
    end = time.monotonic() + 4
    while time.monotonic() < end:
        if visible() == expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"Overlay visible != {expected}")


call("shell", "am", "start", "-W", "-n", package + "/.MainActivity")
click("SHOW THAI TEST SUBTITLE")
wait_visible(True)
call("shell", "input", "keyevent", "KEYCODE_HOME")
# UI is asynchronous: allow composition after verified WindowManager attachment.
time.sleep(0.5)
Path("docs/evidence").mkdir(parents=True, exist_ok=True)
Path("docs/evidence/emulator-m0.png").write_bytes(call("exec-out", "screencap", "-p"))
raw = call("shell", "run-as", package, "cat", "shared_prefs/settings.xml")
token = ET.fromstring(raw).find("string[@name='token']").text
port = call("forward", "tcp:0", "tcp:8765").decode().strip()
url = f"http://127.0.0.1:{port}"
headers = {"Authorization": "Bearer " + token}
try:
    with httpx.Client(timeout=2, trust_env=False) as client:
        assert client.get(url + "/health").status_code == 401
        assert client.get(url + "/health", headers=headers).status_code == 200
        caption = Caption.new("เราต้องออกจากที่นี่ก่อนรุ่งสาง", 1000)
        response = client.post(url + "/v1/captions", headers=headers, json=caption.payload())
        assert response.status_code == 202
        assert (
            client.post(url + "/v1/captions", headers=headers, json=caption.payload()).json()[
                "status"
            ]
            == "duplicate"
        )
        wait_visible(True)
        wait_visible(False)
        long = Caption.new("อยู่ใกล้ฉันไว้", 15000)
        assert (
            client.post(url + "/v1/captions", headers=headers, json=long.payload()).status_code
            == 202
        )
        wait_visible(True)
        time.sleep(0.2)
        Path("docs/evidence/emulator-lan.png").write_bytes(call("exec-out", "screencap", "-p"))
        client.post(
            url + "/v1/captions", headers=headers, json=Caption.new("").payload()
        ).raise_for_status()
        wait_visible(False)
        print("PASS: local M0, background overlay, auth, UTF-8, duplicate id, expiry, hide")
    call("shell", "am", "start", "-W", "-n", package + "/.MainActivity")
    click("STOP SERVICE")
    wait_visible(False)
    try:
        httpx.get(url + "/health", headers=headers, timeout=1, trust_env=False)
        raise AssertionError("Server remained open after stop")
    except httpx.TransportError:
        print("PASS: Stop Service closes listener")
finally:
    call("forward", "--remove", "tcp:" + port)
    call("shell", "input", "keyevent", "KEYCODE_HOME")
