"""
When the user types an unknown command, ask the AI to either:
  A) Suggest the correct existing command (typo / wrong syntax)
  B) Offer to write a new command and register it automatically
"""
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax

console = Console()
err = Console(stderr=True)

BASE_DIR = Path(__file__).resolve().parents[1]
MAIN_PY = BASE_DIR / "cli" / "main.py"

# All top-level commands and sub-commands with their descriptions
COMMAND_HELP = """
provenance people list                     List all people
provenance people add NAME [--role] [--org] [--email] [--context] [--notes] [--tags]
provenance people show SLUG                Show a person's details
provenance people meetings SLUG            List meetings for a person
provenance meetings list [--person] [--after] [--before]
provenance meetings add --title --date [--attendees] [--summary] [--tags]
provenance meetings show SLUG
provenance actions list [--status] [--person]
provenance actions add DESCRIPTION [--due] [--person] [--meeting] [--tags]
provenance actions done ID
provenance docs list
provenance docs import FILE [--title] [--tags] [--notes]
provenance docs add TITLE --file FILE [--tags] [--notes]
provenance docs show SLUG
provenance search QUERY [--db] [--notes] [--sem] [--lex] [--topk] [--context]
provenance ask QUESTION...                 Search CRM + notes then answer via AI (no quotes needed)
provenance note TEXT...                    Freeform capture — AI extracts people/meetings/actions
provenance note TITLE (piped)              Save piped content as a markdown note
provenance extract SOURCE [--dry-run]      Extract and import all people from a document or org chart
provenance ai INSTRUCTION (piped)          Send piped context + instruction to AI
provenance index                           Build/refresh the ck semantic search index
provenance doctor                          Check all dependencies and config
"""

_SYSTEM = f"""\
You are an assistant for the "provenance" CLI tool — a local personal CRM.
The user typed a command that wasn't recognized.

Available commands:
{COMMAND_HELP}

Determine which case applies:

A) TYPO / WRONG SYNTAX — the user meant an existing command. Suggest the correct one.
B) NEW FUNCTIONALITY — this is genuinely new. Design a new command and write the Python code for it.

Respond with ONLY valid JSON in one of these shapes:

Case A:
{{
  "type": "suggest",
  "message": "one-sentence explanation",
  "suggested_command": "provenance ..."
}}

Case B:
{{
  "type": "new",
  "message": "one-sentence explanation of what this new command would do",
  "command_name": "the-command-name",
  "register_line": "app.command(\\"the-command-name\\")(module.function_name)",
  "module": "capture",
  "code": "def function_name(...):\\n    \\"\\"\\"Docstring.\\"\\"\\"\\n    ...full working implementation..."
}}

For case B, the code must be a complete, working Python function following the same patterns
as the existing commands (typer arguments, rich console output, lazy Django model imports).
The module must be one of: people, meetings, actions, search, ai, capture, docs.\
"""


def handle_unknown_command(user_args: list[str]) -> None:
    user_input = "provenance " + " ".join(user_args)

    try:
        from ai.registry import get_provider
        provider = get_provider()
    except Exception:
        # AI not configured — just exit silently (Click already printed the error)
        sys.exit(2)

    err.print(f"\n[dim]Unknown command — asking AI for help…[/dim]")

    try:
        response = provider.complete(system=_SYSTEM, user=f"User typed: {user_input}")
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        data = json.loads(cleaned)
    except Exception:
        sys.exit(2)

    piped = not sys.stdout.isatty()

    if data.get("type") == "suggest":
        console.print(f"\n[yellow]Did you mean?[/yellow]  [bold]{data['suggested_command']}[/bold]")
        if data.get("message"):
            console.print(f"[dim]{data['message']}[/dim]")

        if not piped and typer.confirm("\nRun it?", default=True):
            import shlex, subprocess
            cmd = shlex.split(data["suggested_command"].replace("provenance", sys.argv[0], 1))
            subprocess.run(cmd)

    elif data.get("type") == "new":
        console.print(f"\n[yellow]New command suggested:[/yellow] [bold]provenance {data['command_name']}[/bold]")
        console.print(f"[dim]{data['message']}[/dim]\n")

        code = data.get("code", "")
        if code:
            console.print(Syntax(code, "python", theme="monokai", line_numbers=True))

        if piped or not typer.confirm("\nAdd this command to provenance?", default=False):
            sys.exit(0)

        _write_command(
            module=data["module"],
            code=code,
            command_name=data["command_name"],
            register_line=data["register_line"],
        )

    sys.exit(0)


def _write_command(module: str, code: str, command_name: str, register_line: str) -> None:
    module_path = BASE_DIR / "cli" / "commands" / f"{module}.py"

    if not module_path.exists():
        err.print(f"[red]Module file not found: {module_path}[/red]")
        sys.exit(1)

    # Append the new function to the module
    existing = module_path.read_text()
    module_path.write_text(existing.rstrip() + "\n\n\n" + code + "\n")
    console.print(f"[green]Written[/green] to {module_path.relative_to(BASE_DIR)}")

    # Register in main.py before the doctor/index lines
    main_text = MAIN_PY.read_text()
    insert_before = 'app.command("doctor")'
    new_line = f'{register_line}\n'
    if command_name not in main_text:
        main_text = main_text.replace(insert_before, new_line + insert_before)
        MAIN_PY.write_text(main_text)
        console.print(f"[green]Registered[/green] in cli/main.py")

    console.print(f"\n[bold green]Done.[/bold green] Try: [bold]provenance {command_name} --help[/bold]")
