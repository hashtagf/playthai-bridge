# PlayThai Bridge

**ซับไทยและเสียงไทยจาก Mac ไป Android TV ขณะเล่น PS5 ผ่าน HDMI**

โปรเจกต์ทดลองสำหรับส่งคำแปลจาก Leonida หรือระบบ OCR/AI ของเราไปแสดงบนทีวี
Mac เป็นตัวประมวลผล ส่วน APK บน Android TV แสดงซับและรับเสียงผ่าน LAN
ไม่ใช่ผลิตภัณฑ์อย่างเป็นทางการของ Sony, PlayStation หรือ Leonida

## เลือกโหมดใช้งาน

| โหมด | สิ่งที่ต้องเปิดบน Mac | สถานะ |
|---|---|---|
| Leonida → ซับทีวี | Leonida และ Web Viewer | เชื่อม SSE ได้แล้ว; ยังต้องตรวจส่งซับใหม่ถึงทีวีจริง |
| Leonida → ซับ + เสียงทีวี | เพิ่มอ่านออกเสียง และ `--audio` | ทดลอง; ยังไม่ยืนยันการจับเสียง TTS จริงและเสียงขณะเปิด HDMI |
| Remote Play → OCR → AI | Remote Play, Ollama | อ่านซับอังกฤษ/แชท/มือถือในเกมได้ตามพื้นที่ที่ตั้ง |
| Remote Play → เสียง + OCR → AI | เพิ่ม whisper.cpp | Hybrid ให้ OCR มาก่อน แล้วใช้เสียงเติมช่วงไม่มีซับ |

**เสียงทีวีต้องใช้ APK 0.2.0 ขึ้นไป**; Mac package ปัจจุบัน 0.6.0
การแสดง overlay และการผสมเสียงขณะดู HDMI ขึ้นกับรุ่นทีวี ยังไม่รับรองทุกเครื่อง

## 1. เตรียมโปรเจกต์บน Mac

ต้องมี Python 3.12+, [uv](https://docs.astral.sh/uv/) และ Git
โหมดจับภาพ/เสียงแอปใช้ macOS 14+ และ Xcode Command Line Tools

```sh
git clone https://github.com/hashtagf/playthai-bridge.git
cd playthai-bridge
uv sync --project apps/mac-translator --locked
xcode-select --install  # เฉพาะเครื่องที่ยังไม่มี Command Line Tools
```

อนุญาต Screen Recording ให้ Terminal/แอปที่ใช้รันเมื่อ macOS ขอ แล้วเปิดโปรแกรมใหม่
สำหรับ Leonida ให้ติดตั้งแยกจาก [เว็บไซต์ผู้พัฒนา](https://www.leonidasubth.com/)
โปรเจกต์นี้ไม่รวมแอปหรือคลังคำแปลของ Leonida

## 2. ติดตั้ง APK บน Android TV

APK สำหรับทดสอบอยู่ใน GitHub Actions → Build and test → Android artifact
หรือสร้างเองตาม [คู่มือนักพัฒนา](docs/DEVELOPMENT.md)
แตก ZIP ก่อนติดตั้งไฟล์ `tv-overlay-debug.apk`

```sh
adb connect TV_IP:5555   # ใช้ที่อยู่/พอร์ตที่ทีวีแสดง; บางเครื่องต้อง adb pair ก่อน
adb install -r /path/to/tv-overlay-debug.apk
```

1. เปิด **PlayThai Bridge** บนทีวี → **Request Overlay Permission** และอนุญาต
2. กด **Start Service** → **Show Thai Test Subtitle** แล้วสลับไป HDMI ของ PS5
3. ถ้าซับไม่ปรากฏเหนือ HDMI ให้ใช้หน้าดูซับบน Mac แทนและตรวจ [M0 guide](docs/M0_INSTALL.md)
4. จด IP และ token จากหน้าจอแอปทีวี ห้ามแชร์ภาพ token
5. ถ้าต้องการเสียง กด **Enable Thai Audio** ทุกครั้งหลังเริ่ม service

Debug APK จาก CI อาจใช้ signing key ต่างจาก APK ที่เคยติดตั้ง ถ้าอัปเดตแล้วขึ้น
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` ให้ใช้ APK ที่เซ็นด้วย key เดิม หรือถอนตัวเก่า
แล้วติดตั้งใหม่ (จะสูญเสียการตั้งค่าและ token ต้องจับคู่ใหม่)

## 3. เชื่อม Leonida กับทีวี

Mac และทีวีต้องอยู่ LAN ที่เข้าถึงกันได้ เปิด Leonida เชื่อม Remote Play ตามคู่มือของแอป
แล้วเปิด **Web Viewer** และเปิด **อ่านออกเสียง** หากจะใช้เสียง

จากโฟลเดอร์โปรเจกต์ ใช้ Terminal แบบ zsh บน Mac:

```sh
export TV_IP=192.168.1.119        # เปลี่ยนให้ตรงทีวีปัจจุบัน
export MAC_LAN_IP=192.168.1.61   # เปลี่ยนให้ตรง Mac ปัจจุบัน ไม่ใช่ IP ของทีวี
read -s 'PS5_TV_TOKEN?ใส่ token จากทีวี: '
export PS5_TV_TOKEN
uv run --project apps/mac-translator send-test-caption --tv-host "$TV_IP" --text "ทดสอบซับไทยจาก Mac"

# ส่งเฉพาะซับ
uv run --project apps/mac-translator leonida-tv-bridge --source "$MAC_LAN_IP" --target "$TV_IP"
```

เปิด `http://127.0.0.1:8766` เพื่อดู preview บน Mac ได้ด้วย
ตัวส่งรอข้อความใหม่ ไม่ส่งประวัติเก่าตอนเชื่อมต่อ หากต้องการทดสอบโดยไม่มีทีวีให้ตัด `--target` ออก
ใช้ LAN IP ของ Mac ที่เปิดหน้า Leonida พอร์ต 8765 ได้จริง; IP ของ VPN อาจใช้ไม่ได้
หยุดตัวส่งเดิมด้วย Ctrl-C ก่อนเปลี่ยนโหมด

### เพิ่มเสียง (ทดลอง)

```sh
# ระหว่างตรวจ ให้กดทดลองฟังใน Leonida
uv run --project apps/mac-translator leonida-audio-check --seconds 15

# หลังเปิด Enable Thai Audio บนทีวี
uv run --project apps/mac-translator leonida-tv-bridge --source "$MAC_LAN_IP" --target "$TV_IP" --audio
```

ถ้า peak เป็นศูนย์ทั้งที่ Mac พูดอยู่ ยังใช้เส้นทางนี้ไม่ได้: เสียง TTS อาจออกจาก process อื่น
ตัวจับเสียงจำกัดเฉพาะ Leonida ไม่จับเสียงระบบทั้งหมดเป็นทางเลี่ยง
ยังไม่มีค่าความหน่วง end-to-end ที่วัดกับทีวีจริง; แพ็กเก็ต 100ms ไม่ใช่เวลารวม
รายละเอียดใน [คู่มือเสียง Leonida](docs/LEONIDA_AUDIO.md)

หยุดด้วย Ctrl-C และ **Mute Thai Audio** / **Stop Service** บนทีวี

## 4. ใช้ AI ของเราแทน Leonida

ตั้ง Ollama + OpenThai และ whisper.cpp ตาม [คู่มือติดตั้ง AI](docs/DEVELOPMENT.md#local-ai-on-apple-silicon)
เปิด PS Remote Play ให้เห็นภาพเกมและซับอังกฤษ จากนั้น:

```sh
# อ่านซับจากภาพอย่างเดียว ไม่ต้องใช้ Whisper
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-ocr --target "$TV_IP" --model openthai

# อ่านซับ + แชท + มือถือในเกม และฟังเสียงพร้อมกัน
uv run --project apps/mac-translator ps5-thai-sub run --input remote-play-hybrid --ocr-chat --ocr-phone --target "$TV_IP" --model openthai
```

พื้นที่ OCR ต้องปรับให้ตรงเกม/ขนาดหน้าต่าง ไม่ได้รู้ตำแหน่งแชททุกเกมอัตโนมัติ
ดู [OCR](docs/REMOTE_PLAY_OCR.md), [เสียง Remote Play](docs/REMOTE_PLAY_AUDIO.md),
[Hybrid](docs/HYBRID.md) และ [ผลเปรียบเทียบโมเดล](docs/TRANSLATION_COMPARISON.md)
OpenThai เป็นค่าเริ่มต้น เปลี่ยนเป็น `--model gemma` ได้; AI ยังแปลผิดได้
อย่าเปิดตัวส่งหลายตัวไปทีวีเดียวกันพร้อมกัน

## แก้ปัญหาเบื้องต้น

| อาการ | ตรวจอะไร |
|---|---|
| 401 | token ปัจจุบันจากแอปทีวี |
| ต่อทีวีไม่ได้ | Start Service, IP ปัจจุบัน, Wi-Fi isolation/firewall, TCP 8765 |
| เสียง 404 | APK เก่า ต้องอัปเดต 0.2.0 |
| เสียง 409 | กด Enable Thai Audio; ตรวจ service/session |
| ซับไม่ขึ้นตอนเปิด HDMI | ทดสอบ overlay เฉพาะรุ่น; ใช้ Mac preview หากถูกบล็อก |
| ไม่เห็นซับทันทีหลังเชื่อม Leonida | รอประโยคใหม่; ไม่ replay ประวัติ |
| เสียง/ซับช้า | ตรวจคิวอ่านออกเสียง Leonida หรือเวลา AI; ยังไม่มี SLA ความหน่วง |

HTTP ระหว่าง Mac–TV ไม่เข้ารหัส ใช้เฉพาะ LAN ที่เชื่อถือได้ ไม่เปิดพอร์ตออกอินเทอร์เน็ต
ไม่เก็บ token ใน Git; `.env` ไม่ถูกโหลดอัตโนมัติ

## พัฒนาและตรวจสอบ

[Build/test และ AI setup](docs/DEVELOPMENT.md) · [ผลทดสอบ](TEST_REPORT.md) ·
[ข้อจำกัด](KNOWN_LIMITATIONS.md) · [รายการตรวจฮาร์ดแวร์](docs/MANUAL_ACCEPTANCE.md)

ล่าสุดผ่าน 66 Python tests, 7 Android JVM tests, mypy, Ruff และ build/lint APK
การทดสอบอัตโนมัติไม่ยืนยันเสียง Leonida จริง, HDMI audio mixing, ARC/eARC,
คุณภาพคำแปลหรือ latency ระหว่างเล่นจริง ยังต้องตรวจบน Mac/ทีวีของผู้ใช้
