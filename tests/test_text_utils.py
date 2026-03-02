import cli.text_utils as text_utils


def _reset_enabled(monkeypatch):
    monkeypatch.setattr(text_utils, "_enabled", False)


def test_enable_sets_global_flag(monkeypatch):
    _reset_enabled(monkeypatch)
    assert text_utils.is_enabled() is False

    text_utils.enable()

    assert text_utils.is_enabled() is True


def test_check_returns_input_when_disabled(monkeypatch):
    _reset_enabled(monkeypatch)
    assert text_utils.check("keep this") == "keep this"


def test_check_skips_blank_text_even_when_enabled(monkeypatch):
    _reset_enabled(monkeypatch)
    text_utils.enable()
    assert text_utils.check("   ") == "   "


def test_check_returns_corrected_text_when_enabled(monkeypatch):
    _reset_enabled(monkeypatch)
    text_utils.enable()
    monkeypatch.setattr("ai.text_checker.correct_texts", lambda texts: ["fixed text"])

    assert text_utils.check("fixd text") == "fixed text"


def test_check_falls_back_to_original_on_runtime_error(monkeypatch):
    _reset_enabled(monkeypatch)
    text_utils.enable()

    def raise_runtime_error(_):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("ai.text_checker.correct_texts", raise_runtime_error)
    assert text_utils.check("original text") == "original text"
