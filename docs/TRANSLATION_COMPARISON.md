# Gemma versus OpenThai local translation trial — 2026-11-22

Tested `gemma3:4b` and `openthai/openthai-1.5-7b` (7.6B Q4_K_M) on this M4 Max Mac.
The OpenThai tag comes from the [official model card](https://huggingface.co/openthaigpt/openthaigpt1.5-7b-instruct).
Model download is about 4.7 GB and remains in Ollama for repeat experiments; production
model selection was not changed by this trial. In a later user-requested update,
OpenThai became the default with a Gemma preset available; the quality findings below
remain unchanged.

## Method

12 authored English game-like lines, repeated twice per model: 8 independent sentences
and a 4-line contextual sequence. Production APITranslator prompt, temperature=0,
max_tokens=400, same provider and machine, models measured sequentially. Application
translation cache cleared for each request. Separate warm-up excluded from percentiles.
Ollama model-specific templates/default context sizes are retained (not an equal-parameter
architecture benchmark). No OCR, TV transport or panel latency is included.

| Model | Requests | Warm-up | Warm p50 | Warm p95 | Client validation failures |
|---|---:|---:|---:|---:|---:|
| Gemma 3 4B | 24 | 3.30s | 0.175s | 0.270s | 0 |
| OpenThai 1.5 7B | 24 | 5.77s | 0.273s | 0.594s | 0 |

Zero client validation failures only means bounded output containing Thai passed the
current guard; it does NOT imply correct translation. Both produced identical outputs
in the two repetitions for each fixture. Sample size is small, not a general benchmark.

## Qualitative observations (agent review, not blinded human evaluation)

- `Don't shoot. He's on our side.`: OpenThai correctly returned `อย่ายิง เขาอยู่ฝ่ายเรา`;
  Gemma returned `อย่าลงโทษเขา เขาอยู่ข้างเรา` (punish, not shoot).
- `Stay close to me.`: Gemma returned `อยู่ใกล้ฉันด้วยนะ`; OpenThai appended Chinese text.
- `I didn't say he stole the key.`: Gemma preserved the meaning; OpenThai returned a
  malformed mixed-script phrase (`ฉันไม่ได้บอกว่าเขารobkeyไป`).
- `Target down. Head for an exit.`: both misread the idiomatic elimination status.
- Neither consistently preserved the English spelling of the proper name Diana.

A further 12 requests per model used the SAME explicit Thai-language translation prompt
for both. p50/p95: Gemma 0.320/0.809s; OpenThai 0.503/1.222s. Some phrases improved, but
OpenThai still emitted Chinese, English fragments or malformed text; Gemma still mistranslated
some game terms. This prompt change was experimental and was not deployed.

Conclusion: **do not replace Gemma with this OpenThai model on the basis of this trial**.
Both need broader translation-quality work. This does not evaluate every OpenThai version
or a specially fine-tuned translation model. Full outputs, references and per-request times:
[evidence/translation-comparison.json](evidence/translation-comparison.json).

## Live OCR diagnosis

The Remote Play capture still displayed the same PS5 controller-user chooser rather
than current game dialogue. Three additional subtitle-region reads produced empty text;
there were no successful live OCR captions in the session log. A concurrent diagnostic
capture initially failed; sequential captures after pausing the main reader succeeded.
The diagnostic screenshot was deleted, not committed. The issue prevents measuring real
subtitle-to-TV latency regardless of translator. OCR needs a moving game stream with
visible English subtitles before a meaningful real-game comparison can be made.

OCR was paused to avoid competing with model timings, then resumed with the original
Gemma configuration. No controller inputs, account changes or console settings were made.

Repeat from repository root:
```sh
uv run --project apps/mac-translator python scripts/compare_translators.py
uv run --project apps/mac-translator python scripts/compare_translators.py --thai-prompt --rounds 1 --output artifacts/thai-prompt-comparison.json
```
Normal application logs do not contain live transcripts. The comparison deliberately
records only authored fixtures, never captured gameplay dialogue.
