from core.management.commands.import_docs import _tags_from_filename, _title_from_file


def test_title_from_file_uses_first_markdown_heading(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("intro line\n# Actual Title\n## Other Heading\n")

    assert _title_from_file(path) == "Actual Title"


def test_title_from_file_falls_back_to_filename(tmp_path):
    path = tmp_path / "q1_planning-notes.md"
    path.write_text("plain text with no headings")

    assert _title_from_file(path) == "Q1 Planning Notes"


def test_tags_from_filename_matches_multiple_rules_case_insensitive():
    name = "Wharton-Research_Playbook-Resume.md"
    assert _tags_from_filename(name) == "resume, research, wharton"


def test_tags_from_filename_returns_empty_for_non_matches():
    assert _tags_from_filename("daily-notes.md") == ""
