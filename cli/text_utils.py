"""
Lightweight text-correction helper used by individual commands.

The --check-text / -ct flag is stripped in arg_normalizer and stored here.
Commands call check() on specific prose fields after Typer has validated args,
so a bad flag or missing option fails immediately without an API call.
"""

from rich.console import Console

_enabled = False
_err = Console(stderr=True)


def enable() -> None:
    global _enabled
    _enabled = True


def is_enabled() -> bool:
    return _enabled


def check(text: str) -> str:
    """Return corrected text if --check-text is active, otherwise return as-is."""
    if not _enabled or not text or not text.strip():
        return text

    try:
        from ai.text_checker import correct_texts
        results = correct_texts([text])
        corrected = results[0] if results else text
    except RuntimeError as e:
        _err.print(f"[red]--check-text failed:[/red] {e}")
        _err.print("[yellow]Continuing with original text.[/yellow]")
        return text

    if corrected != text:
        _err.print(f"  [yellow]~[/yellow] {text!r}")
        _err.print(f"  [green]✓[/green] {corrected!r}")

    return corrected
