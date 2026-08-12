"""Phase 1 command-line entry point."""

import argparse

from rich.console import Console
from rich.table import Table

from crypto_agent.config import get_settings


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only crypto market analysis agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-config", help="Validate local settings without showing secrets")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "check-config":
        check_config()
