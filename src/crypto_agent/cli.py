"""Configuration and Phase 4 graph-debug commands."""

import argparse
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.table import Table

from crypto_agent.config import get_settings
from crypto_agent.graph import build_crypto_agent


def check_config() -> None:
    """Validate configuration while revealing no credential values."""

    settings = get_settings()
    table = Table(title="Crypto Analysis Agent configuration")
    table.add_column("Setting")
    table.add_column("Status")
    table.add_row("OpenAI API key", "configured")
    table.add_row("FreeCryptoAPI key", "configured")
    table.add_row("NewsAPI key", "configured")
    table.add_row("OpenAI model", settings.openai_model)
    table.add_row("Request timeout", f"{settings.request_timeout_seconds:g} seconds")
    table.add_row("Maximum HTTP retries", str(settings.max_http_retries))
    table.add_row("LangSmith tracing", "enabled" if settings.langsmith_tracing else "disabled")
    Console().print(table)


def debug_graph(prompt: str) -> None:
    """Stream observable graph nodes for one stateless test question."""
    console = Console()
    with build_crypto_agent() as agent:
        for update in agent.graph.stream(
            {"messages": [HumanMessage(content=prompt)]},
            stream_mode="updates",
        ):
            for node, payload in update.items():
                messages = payload.get("messages", [])
                if node == "model" and messages:
                    message = messages[-1]
                    if isinstance(message, AIMessage) and message.tool_calls:
                        for call in message.tool_calls:
                            arguments = json.dumps(call["args"], sort_keys=True)
                            console.print(f"[cyan]model → tool:[/cyan] {call['name']} {arguments}")
                    elif isinstance(message, AIMessage):
                        console.print(f"[green]answer:[/green] {message.text}")
                elif node == "tools":
                    count = sum(isinstance(message, ToolMessage) for message in messages)
                    console.print(f"[cyan]tools → model:[/cyan] {count} result(s)")
                elif node == "tool_limit":
                    console.print("[yellow]tool-call limit reached[/yellow]")
                elif node == "duplicate_tool":
                    console.print("[yellow]duplicate tool call rejected[/yellow]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only crypto market analysis agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-config", help="Validate local settings without showing secrets")
    debug = subcommands.add_parser("debug", help="Run one stateless graph routing trace")
    debug.add_argument("prompt", help="Question to send through the graph")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "check-config":
        check_config()
    elif args.command == "debug":
        debug_graph(args.prompt)
