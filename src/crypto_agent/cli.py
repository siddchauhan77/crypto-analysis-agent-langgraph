"""Configuration, graph debugging, and persistent chat commands."""

import argparse
import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from rich.console import Console
from rich.table import Table

from crypto_agent.config import get_settings
from crypto_agent.evaluation import run_live_evaluation
from crypto_agent.graph import build_crypto_agent, build_persistent_crypto_agent
from crypto_agent.memory import (
    get_thread_messages,
    new_thread_id,
    thread_config,
    validate_thread_id,
)


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


def stream_turn(
    graph: CompiledStateGraph,
    prompt: str,
    console: Console,
    config: RunnableConfig | None = None,
) -> None:
    """Stream concise routing updates and the final answer for one turn."""
    for update in graph.stream(
        {"messages": [HumanMessage(content=prompt)]},
        config=config,
        stream_mode="updates",
    ):
        for node, payload in update.items():
            messages = payload.get("messages", [])
            if node == "model" and messages:
                message = messages[-1]
                if isinstance(message, AIMessage) and message.tool_calls:
                    for call in message.tool_calls:
                        arguments = json.dumps(call["args"], sort_keys=True)
                        console.print(f"[cyan]Using {call['name']}[/cyan] {arguments}")
                elif isinstance(message, AIMessage):
                    console.print(f"[green]Agent:[/green] {message.text}")
            elif node == "tools":
                count = sum(isinstance(message, ToolMessage) for message in messages)
                console.print(f"[cyan]Received {count} tool result(s)[/cyan]")
            elif node == "tool_limit":
                console.print("[yellow]Tool-call limit reached[/yellow]")
            elif node == "duplicate_tool":
                console.print("[yellow]Duplicate tool call rejected[/yellow]")


def debug_graph(prompt: str) -> None:
    """Stream observable graph nodes for one stateless test question."""
    with build_crypto_agent() as agent:
        stream_turn(agent.graph, prompt, Console())


def print_chat_help(console: Console) -> None:
    """Show commands available inside persistent chat."""
    console.print(
        "[bold]Commands[/bold]\n"
        "  new                 Start a fresh thread\n"
        "  resume THREAD_ID    Switch to an existing or named thread\n"
        "  history             Show this thread's conversation\n"
        "  help                Show these commands\n"
        "  quit                 Exit"
    )


def print_history(graph: CompiledStateGraph, thread_id: str, console: Console) -> None:
    """Print user and final agent messages without exposing raw tool payloads."""
    messages = get_thread_messages(graph, thread_id)
    visible = [
        message
        for message in messages
        if isinstance(message, HumanMessage)
        or (isinstance(message, AIMessage) and not message.tool_calls and message.text)
    ]
    if not visible:
        console.print("[dim]No conversation history for this thread.[/dim]")
        return
    for message in visible:
        label = "You" if isinstance(message, HumanMessage) else "Agent"
        console.print(f"[bold]{label}:[/bold] {message.text}")


def interactive_chat(initial_thread_id: str | None = None) -> None:
    """Run a resumable, SQLite-backed terminal conversation."""
    console = Console()
    try:
        active_thread = (
            validate_thread_id(initial_thread_id) if initial_thread_id else new_thread_id()
        )
    except ValueError as exc:
        console.print(f"[red]Invalid thread ID:[/red] {exc}")
        return

    try:
        with build_persistent_crypto_agent() as agent:
            console.print(
                f"[bold]Crypto Analysis Agent[/bold]  Thread: [cyan]{active_thread}[/cyan]"
            )
            console.print(
                "Type [bold]help[/bold] for commands. Analysis only, not financial advice."
            )
            while True:
                try:
                    prompt = console.input("\n[bold]You:[/bold] ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Chat closed.[/dim]")
                    break
                if not prompt:
                    continue
                command, _, argument = prompt.partition(" ")
                command = command.lower()
                if command in {"quit", "exit"} and not argument:
                    console.print("[dim]Chat closed.[/dim]")
                    break
                if command == "help" and not argument:
                    print_chat_help(console)
                    continue
                if command == "history" and not argument:
                    print_history(agent.graph, active_thread, console)
                    continue
                if command == "new" and not argument:
                    active_thread = new_thread_id()
                    console.print(f"New thread: [cyan]{active_thread}[/cyan]")
                    continue
                if command == "resume":
                    try:
                        active_thread = validate_thread_id(argument)
                    except ValueError as exc:
                        console.print(f"[red]Invalid thread ID:[/red] {exc}")
                        continue
                    message_count = len(get_thread_messages(agent.graph, active_thread))
                    status = "resumed" if message_count else "ready"
                    console.print(
                        f"Thread [cyan]{active_thread}[/cyan] {status}. "
                        f"{message_count} stored message(s)."
                    )
                    continue
                try:
                    stream_turn(
                        agent.graph,
                        prompt,
                        console,
                        thread_config(active_thread),
                    )
                except Exception as exc:
                    console.print(f"[red]Request failed:[/red] {exc}")
                    console.print("Your thread remains saved. Retry or type quit.")
    except Exception as exc:
        console.print(f"[red]Unable to start chat:[/red] {exc}")


def evaluate_agent(cases: Path, output: Path, repetitions: int, live: bool) -> None:
    """Run the fixed evaluation dataset with explicit quota consent."""
    console = Console()
    if not live:
        console.print("[yellow]Evaluation not started.[/yellow]")
        console.print("Add --live to permit OpenAI, FreeCryptoAPI, and NewsAPI requests.")
        return
    console.print(
        f"Running [bold]{repetitions}[/bold] repetition(s) of cases from [cyan]{cases}[/cyan]."
    )
    report = run_live_evaluation(cases, output, repetitions=repetitions)
    summary = report["summary"]
    table = Table(title="Evaluation baseline")
    table.add_column("Metric")
    table.add_column("Result")
    table.add_row("Passed runs", f"{summary['passed_runs']} / {summary['total_runs']}")
    table.add_row("Pass rate", f"{summary['pass_rate']:.1%}")
    table.add_row("Median latency", f"{summary['median_latency_seconds']:.3f} seconds")
    cost = summary["estimated_model_cost_usd"]
    table.add_row("Estimated model cost", "unavailable" if cost is None else f"${cost:.6f}")
    table.add_row("Saved report", str(output))
    console.print(table)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only crypto market analysis agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-config", help="Validate local settings without showing secrets")
    debug = subcommands.add_parser("debug", help="Run one stateless graph routing trace")
    debug.add_argument("prompt", help="Question to send through the graph")
    chat = subcommands.add_parser("chat", help="Start or resume a persistent conversation")
    chat.add_argument("--thread", help="Thread ID to resume or create")
    evaluate = subcommands.add_parser("evaluate", help="Run the fixed live evaluation dataset")
    evaluate.add_argument("--cases", type=Path, default=Path("evals/cases.jsonl"))
    evaluate.add_argument("--output", type=Path, default=Path("evals/baseline-results.json"))
    evaluate.add_argument("--repetitions", type=int, default=2)
    evaluate.add_argument(
        "--live",
        action="store_true",
        help="Permit paid model and quota-limited provider requests",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "check-config":
        check_config()
    elif args.command == "debug":
        debug_graph(args.prompt)
    elif args.command == "chat":
        interactive_chat(args.thread)
    elif args.command == "evaluate":
        evaluate_agent(args.cases, args.output, args.repetitions, args.live)
