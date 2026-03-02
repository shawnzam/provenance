import json

import ai.text_checker as text_checker


class _StubProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def complete(self, system: str, user: str, model: str | None = None) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        return self.response


def test_correct_texts_returns_empty_for_empty_input(monkeypatch):
    def should_not_be_called():
        raise AssertionError("get_provider should not be called for empty input")

    monkeypatch.setattr(text_checker, "get_provider", should_not_be_called)
    assert text_checker.correct_texts([]) == []


def test_correct_texts_parses_valid_json_and_uses_model_from_env(monkeypatch):
    provider = _StubProvider('["fixed typo"]')
    monkeypatch.setattr(text_checker, "get_provider", lambda: provider)
    monkeypatch.setenv("PROVENANCE_PROOFREAD_AI_MODEL", "proof-model")

    result = text_checker.correct_texts(["fixd typo"])

    assert result == ["fixed typo"]
    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == "proof-model"
    assert json.loads(provider.calls[0]["user"]) == ["fixd typo"]


def test_correct_texts_falls_back_to_originals_on_invalid_json(monkeypatch):
    provider = _StubProvider("not json")
    monkeypatch.setattr(text_checker, "get_provider", lambda: provider)

    original = ["bad text"]
    assert text_checker.correct_texts(original) == original


def test_correct_texts_falls_back_to_originals_on_length_mismatch(monkeypatch):
    provider = _StubProvider('["one"]')
    monkeypatch.setattr(text_checker, "get_provider", lambda: provider)

    original = ["first", "second"]
    assert text_checker.correct_texts(original) == original
