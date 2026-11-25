"""Selectable model presets; explicit CLI choice wins over environment and default."""

import os

PRESETS = {
    "openthai": "openthai/openthai-1.5-7b",
    "gemma": "gemma3:4b",
}
DEFAULT_MODEL = PRESETS["openthai"]


def resolve_model(value: str | None = None) -> str:
    selected = value if value is not None else os.getenv("TRANSLATION_MODEL") or DEFAULT_MODEL
    selected = selected.strip()
    if not selected or any(ord(c) < 32 for c in selected):
        raise ValueError("Model must be a non-empty name without control characters")
    return PRESETS.get(selected.lower(), selected)
