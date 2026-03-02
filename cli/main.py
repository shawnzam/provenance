import sys
from dotenv import load_dotenv
from cli.paths import ENV_FILE

# Load .env before anything — normalizer may call OpenAI for --check-text
load_dotenv(ENV_FILE)

import click
import typer
from cli.arg_normalizer import normalize_args

sys.argv = normalize_args(sys.argv)

from cli.setup_django import setup  # noqa: E402

setup()

from cli.commands import people, meetings, actions, search, ai, docs, capture, chat, reading  # noqa: E402
from cli.commands import init  # noqa: E402

app = typer.Typer(
    name="provenance",
    help="Local-first personal CRM and memory tool.",
    no_args_is_help=True,
)

app.add_typer(people.app, name="people")
app.add_typer(meetings.app, name="meetings")
app.add_typer(actions.app, name="actions")
app.add_typer(docs.app, name="docs")
app.add_typer(reading.app, name="reading")

# Single-command groups registered as commands
app.command("search")(search.search)
app.command("ai")(ai.ai)
app.command("ask")(ai.ask)
app.command("note")(capture.note)
app.command("proof")(ai.proof)
app.command("remember")(capture.remember)
app.command("extract")(capture.extract)
app.command("doctor")(search.doctor)
app.command("index")(search.index_notes_cmd)
app.command("chat")(chat.chat)
app.command("init")(init.init)
app.command("migrate")(init.migrate)


def main():
    try:
        app(standalone_mode=False)
    except click.UsageError as e:
        if "no such command" in str(e).lower():
            args = sys.argv[1:]
            # Natural language (no flags, 2+ words) → treat as `ask`
            if len(args) >= 2 and not any(a.startswith("-") for a in args):
                sys.argv = [sys.argv[0], "ask"] + args
                app(standalone_mode=False)
            else:
                from cli.ai_suggest import handle_unknown_command
                handle_unknown_command(args)
        else:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
    except (click.exceptions.Exit, SystemExit) as e:
        code = e.code if hasattr(e, "code") else 0
        sys.exit(code or 0)
    except click.exceptions.Abort:
        sys.exit(1)


if __name__ == "__main__":
    main()
