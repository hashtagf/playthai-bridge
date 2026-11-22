# Architecture

```mermaid
flowchart LR
  PS5 -->|ordinary HDMI| TV[BRAVIA 9]
  DS[DualSense] -->|direct pairing| PS5
  TV -->|speaker audio| MIC[Mac microphone]
  MIC --> VAD[20ms energy VAD / max 8s chunks]
  VAD --> Q[latest utterance queue: 1]
  Q --> ASR[whisper.cpp local server]
  ASR --> ST[final phrase duplicate suppression]
  ST --> TR[Thai translator / 3 phrase context]
  TR --> VIEW[localhost browser viewer]
  TR --> PUB[bounded HTTP publisher]
  PUB -->|token + LAN| SVC[Android foreground service]
  SVC --> WM[WindowManager Thai TextView]
  WM -. physical feasibility NOT TESTED .-> TV
```

Audio never travels from PS5 electronically to Mac. No capture hardware/Remote Play,
OCR, controller interception or HDMI alteration. The OS may block overlay composition
on HDMI or protected surfaces. Text is drawn only inside the caption region.

The pipeline timestamps the last voiced input frame, then records elapsed time after
publish acknowledgement. Includes silence detection, queue wait, ASR, translation and
transport; excludes physical panel render delay. Demo timings are not microphone data.
Target median ≤3 seconds is aspirational and must be measured with actual game audio.
