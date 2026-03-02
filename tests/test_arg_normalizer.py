import cli.arg_normalizer as arg_normalizer
import cli.text_utils as text_utils


def test_normalize_args_routes_people_slug_to_show():
    argv = ["provenance", "people", "jane-doe"]
    assert arg_normalizer.normalize_args(argv) == [
        "provenance",
        "people",
        "show",
        "jane-doe",
    ]


def test_normalize_args_routes_people_slug_meetings():
    argv = ["provenance", "people", "jane-doe", "meetings"]
    assert arg_normalizer.normalize_args(argv) == [
        "provenance",
        "people",
        "meetings",
        "jane-doe",
    ]


def test_normalize_args_does_not_route_known_subcommand():
    argv = ["provenance", "people", "list"]
    assert arg_normalizer.normalize_args(argv) == argv


def test_normalize_args_does_not_route_people_options():
    argv = ["provenance", "people", "--help"]
    assert arg_normalizer.normalize_args(argv) == argv


def test_normalize_args_strips_check_text_flags_and_enables_once(monkeypatch):
    calls = 0

    def fake_enable():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(text_utils, "enable", fake_enable)

    argv = [
        "provenance",
        "people",
        "add",
        "--name",
        "Jane Doe",
        "--check-text",
        "-ct",
    ]
    assert arg_normalizer.normalize_args(argv) == [
        "provenance",
        "people",
        "add",
        "--name",
        "Jane Doe",
    ]
    assert calls == 1


def test_normalize_args_does_not_mutate_input():
    argv = ["provenance", "people", "jane-doe"]
    original = list(argv)
    arg_normalizer.normalize_args(argv)
    assert argv == original
