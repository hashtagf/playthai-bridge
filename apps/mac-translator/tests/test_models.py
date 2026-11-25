import pytest

from ps5_thai_sub.models import DEFAULT_MODEL, resolve_model


def test_default_is_openthai(monkeypatch):
    monkeypatch.delenv("TRANSLATION_MODEL", raising=False)
    assert resolve_model() == "openthai/openthai-1.5-7b" == DEFAULT_MODEL


def test_presets_and_custom_model():
    assert resolve_model("gemma") == "gemma3:4b"
    assert resolve_model("OpenThai") == DEFAULT_MODEL
    assert resolve_model("my-provider/custom-model") == "my-provider/custom-model"


def test_explicit_choice_wins_over_environment(monkeypatch):
    monkeypatch.setenv("TRANSLATION_MODEL", "gemma")
    assert resolve_model() == "gemma3:4b"
    assert resolve_model("openthai") == DEFAULT_MODEL
    monkeypatch.setenv("TRANSLATION_MODEL", "")
    assert resolve_model() == DEFAULT_MODEL


@pytest.mark.parametrize("value", ["", "   ", "bad\nmodel"])
def test_invalid_model(value):
    with pytest.raises(ValueError):
        resolve_model(value)
