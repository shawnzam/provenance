"""Provenance MCP server — exposes CRM tools to Claude Code and other MCP clients."""
import asyncio
from pathlib import Path

# Must happen before any Django or tool imports
from dotenv import load_dotenv
from cli.paths import ENV_FILE, PROVENANCE_HOME
load_dotenv(ENV_FILE)

from cli.setup_django import setup
setup()

import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent, Prompt, PromptMessage, GetPromptResult
from cli.tools import TOOLS, run_tool

BASE_DIR = PROVENANCE_HOME
server = Server("provenance")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=t["function"]["name"],
            description=t["function"]["description"],
            inputSchema=t["function"]["parameters"],
        )
        for t in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # run_tool is sync Django ORM — offload to thread
    result = await asyncio.to_thread(run_tool, name, arguments or {})
    return [TextContent(type="text", text=result)]


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="my_profile",
            description="Load personal context about the user into this conversation",
        )
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    if name != "my_profile":
        raise ValueError(f"Unknown prompt: {name}")

    sections: list[str] = []

    context_file = BASE_DIR / "notes" / "context.md"
    if context_file.exists():
        ctx = context_file.read_text().strip()
        if ctx:
            sections.append(ctx)

    if not sections:
        text = "No personal context found. Add notes to notes/context.md."
    else:
        text = "\n\n".join(sections)

    return GetPromptResult(
        description="Personal context about the user",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=f"Here is context about me that you should keep in mind:\n\n{text}"),
            )
        ],
    )


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
