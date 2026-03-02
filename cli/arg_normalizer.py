"""
Normalize shorthand CLI invocations before Typer processes them.

Slug routing:
  provenance people <slug>            → provenance people show <slug>
  provenance people <slug> meetings   → provenance people meetings <slug>

Text correction (--check-text / -ct):
  Scans all string values that contain whitespace (prose, not identifiers),
  sends them to the AI provider for spelling/grammar correction, then
  substitutes corrected values back into argv before Typer sees them.
  The flag itself is stripped from argv.
"""

PEOPLE_SUBCOMMANDS = {"list", "add", "show", "meetings", "--help", "-h"}
CHECK_TEXT_FLAGS = {"--check-text", "-ct"}


def normalize_args(argv: list[str]) -> list[str]:
    """Return a potentially modified copy of argv."""
    args = list(argv)

    # --- Strip --check-text / -ct and enable the global flag ---
    # Actual text correction happens inside each command after Typer validates
    # args, so a bad flag or unknown option fails fast with no API call.
    filtered = []
    check_text = False
    for arg in args:
        if arg in CHECK_TEXT_FLAGS:
            check_text = True
        else:
            filtered.append(arg)
    args = filtered

    if check_text:
        from cli.text_utils import enable
        enable()

    # --- Slug routing for `people` subcommand ---
    args = _slug_routing(args)

    return args


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _slug_routing(args: list[str]) -> list[str]:
    if len(args) < 3:
        return args

    script, cmd, *rest = args

    if cmd != "people" or not rest:
        return args

    first = rest[0]
    if first in PEOPLE_SUBCOMMANDS or first.startswith("-"):
        return args

    slug = first
    trailing = rest[1:]

    if trailing and trailing[0] == "meetings":
        return [script, "people", "meetings", slug] + trailing[1:]

    return [script, "people", "show", slug] + trailing


