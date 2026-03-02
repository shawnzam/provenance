from cli.commands.capture import _chunk_text


def test_chunk_text_returns_single_chunk_when_under_limit():
    text = "short text"
    assert _chunk_text(text, chunk_size=100) == [text]


def test_chunk_text_splits_at_paragraph_boundaries():
    text = ("a" * 8) + "\n\n" + ("b" * 8) + "\n\n" + ("c" * 8)
    assert _chunk_text(text, chunk_size=10) == ["a" * 8, "b" * 8, "c" * 8]


def test_chunk_text_keeps_oversized_single_paragraph_together():
    text = "x" * 50
    assert _chunk_text(text, chunk_size=10) == [text]
