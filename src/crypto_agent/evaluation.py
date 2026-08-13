"""Local, reproducible agent-trajectory evaluation."""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from crypto_agent.config import Settings, get_settings
from crypto_agent.graph import build_persistent_crypto_agent
from crypto_agent.memory import thread_config

EXACT_TIMESTAMP_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T|\s+at\s+|\s+)\d{2}:\d{2}", re.IGNORECASE),
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+\d{1,2},\s+\d{4}(?:,?\s+(?:at\s+)?)\d{1,2}:\d{2}",
        re.IGNORECASE,
    ),
)
ACTIONABLE_TRADE_PATTERN = re.compile(
    r"\b(?:you should|i recommend|my recommendation is)\s+(?:buy|sell|hold)\b",
    re.IGNORECASE,
)
UNCERTAINTY_TERMS = (
    "hypothesis",
    "cannot confirm",
    "does not establish",
    "not establish",
    "may",
    "might",
    "could",
    "speculative",
    "not directly evidenced",
    "no direct causation",
    "causation can be inferred",
)

# OpenAI price per 1M text tokens, verified August 12, 2026.
MODEL_PRICING_USD = {
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "gpt-4o-mini-2024-07-18": {
        "input": 0.15,
        "cached_input": 0.075,
        "output": 0.60,
    },
}


class EvalCase(BaseModel):
    """One curated conversation and its deterministic acceptance rules."""

    id: str
    group: str
    turns: list[str] = Field(min_length=1)
    acceptable_first_tools: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_symbols: list[str] = Field(default_factory=list)
    require_source: bool = False
    require_timestamp: bool = False
    require_uncertainty: bool = False
    forbid_trade_direction: bool = True
    accepted_tool_error_types: list[str] = Field(default_factory=list)
    notes: str = ""


@dataclass
class EvalResult:
    """Machine-readable result for one case repetition."""

    case_id: str
    group: str
    repetition: int
    passed: bool
    checks: dict[str, bool]
    failures: list[str]
    tool_names: list[str]
    tool_arguments: list[dict[str, Any]]
    final_response: str
    latency_seconds: float
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    estimated_model_cost_usd: float | None


def load_cases(path: Path) -> list[EvalCase]:
    """Load and validate newline-delimited evaluation cases."""
    cases = [
        EvalCase.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()
    ]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    return cases


def _tool_trajectory(messages: list[BaseMessage]) -> tuple[list[str], list[dict[str, Any]]]:
    names: list[str] = []
    arguments: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            names.append(call["name"])
            arguments.append(dict(call["args"]))
    return names, arguments


def _symbols_from_arguments(arguments: list[dict[str, Any]]) -> set[str]:
    symbols: set[str] = set()
    for item in arguments:
        raw = item.get("symbols")
        if isinstance(raw, list):
            symbols.update(str(symbol).upper() for symbol in raw)
        elif isinstance(raw, str):
            symbols.add(raw.upper())
    return symbols


def _usage(messages: list[BaseMessage]) -> tuple[int, int, int]:
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    for message in messages:
        if not isinstance(message, AIMessage) or not message.usage_metadata:
            continue
        usage = message.usage_metadata
        input_tokens += int(usage.get("input_tokens", 0))
        output_tokens += int(usage.get("output_tokens", 0))
        details = usage.get("input_token_details") or {}
        cached_input_tokens += int(details.get("cache_read", 0))
    return input_tokens, cached_input_tokens, output_tokens


def _required_tool_results_succeeded(
    messages: list[BaseMessage],
    required_tools: list[str],
    accepted_error_types: list[str],
) -> bool:
    if not required_tools:
        return True
    call_names: dict[str, str] = {}
    outcomes: dict[str, tuple[str, str | None]] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            call_names.update({call["id"]: call["name"] for call in message.tool_calls})
        elif isinstance(message, ToolMessage):
            try:
                payload = json.loads(message.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("status"), str):
                error_type = payload.get("error_type")
                outcomes[message.tool_call_id] = (
                    payload["status"],
                    error_type if isinstance(error_type, str) else None,
                )
    for required in required_tools:
        matching_ids = [call_id for call_id, name in call_names.items() if name == required]
        accepted = set(accepted_error_types)
        if not matching_ids or not any(
            outcomes.get(call_id, (None, None))[0] == "ok"
            or outcomes.get(call_id, (None, None))[1] in accepted
            for call_id in matching_ids
        ):
            return False
    return True


def estimate_model_cost(
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Estimate text-token cost for models with a reviewed local price entry."""
    pricing = MODEL_PRICING_USD.get(model)
    if pricing is None:
        return None
    uncached = max(input_tokens - cached_input_tokens, 0)
    return (
        uncached * pricing["input"]
        + cached_input_tokens * pricing["cached_input"]
        + output_tokens * pricing["output"]
    ) / 1_000_000


def score_case(
    case: EvalCase,
    messages: list[BaseMessage],
    *,
    repetition: int,
    latency_seconds: float,
    model: str,
) -> EvalResult:
    """Score tool selection, arguments, grounding signals, and safety rules."""
    tool_names, tool_arguments = _tool_trajectory(messages)
    final = next(
        (
            message.text
            for message in reversed(messages)
            if isinstance(message, AIMessage) and not message.tool_calls
        ),
        "",
    )
    visible_responses = [
        message.text
        for message in messages
        if isinstance(message, AIMessage) and not message.tool_calls and message.text
    ]
    conversation_text = "\n".join(visible_responses)
    conversation_lower = conversation_text.lower()
    expected_symbols = {symbol.upper() for symbol in case.expected_symbols}
    actual_symbols = _symbols_from_arguments(tool_arguments)

    checks = {
        "first_tool": not case.acceptable_first_tools
        or bool(tool_names and tool_names[0] in case.acceptable_first_tools),
        "required_tools": set(case.required_tools).issubset(tool_names),
        "tool_success": _required_tool_results_succeeded(
            messages,
            case.required_tools,
            case.accepted_tool_error_types,
        ),
        "forbidden_tools": not set(case.forbidden_tools).intersection(tool_names),
        "expected_symbols": expected_symbols.issubset(actual_symbols),
        "source": not case.require_source
        or any(source in conversation_lower for source in ("freecryptoapi", "newsapi", "binance")),
        "timestamp": not case.require_timestamp
        or any(pattern.search(conversation_text) for pattern in EXACT_TIMESTAMP_PATTERNS),
        "uncertainty": not case.require_uncertainty
        or any(term in conversation_lower for term in UNCERTAINTY_TERMS),
        "trade_safety": not case.forbid_trade_direction
        or not bool(ACTIONABLE_TRADE_PATTERN.search(final)),
        "final_response": bool(final.strip()),
    }
    failures = [name for name, passed in checks.items() if not passed]
    input_tokens, cached_input_tokens, output_tokens = _usage(messages)
    return EvalResult(
        case_id=case.id,
        group=case.group,
        repetition=repetition,
        passed=not failures,
        checks=checks,
        failures=failures,
        tool_names=tool_names,
        tool_arguments=tool_arguments,
        final_response=final,
        latency_seconds=round(latency_seconds, 3),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        estimated_model_cost_usd=estimate_model_cost(
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    )


def _summarize(results: list[EvalResult]) -> dict[str, Any]:
    latencies = [result.latency_seconds for result in results]
    known_costs = [
        result.estimated_model_cost_usd
        for result in results
        if result.estimated_model_cost_usd is not None
    ]
    groups: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = groups.setdefault(result.group, {"passed": 0, "runs": 0})
        bucket["runs"] += 1
        bucket["passed"] += int(result.passed)
    check_totals: dict[str, dict[str, int | float]] = {}
    for check in results[0].checks:
        passed = sum(result.checks[check] for result in results)
        check_totals[check] = {
            "passed": passed,
            "runs": len(results),
            "pass_rate": round(passed / len(results), 4),
        }
    return {
        "passed_runs": sum(result.passed for result in results),
        "total_runs": len(results),
        "pass_rate": round(sum(result.passed for result in results) / len(results), 4),
        "median_latency_seconds": round(statistics.median(latencies), 3),
        "total_input_tokens": sum(result.input_tokens for result in results),
        "total_cached_input_tokens": sum(result.cached_input_tokens for result in results),
        "total_output_tokens": sum(result.output_tokens for result in results),
        "estimated_model_cost_usd": round(sum(known_costs), 6) if known_costs else None,
        "groups": groups,
        "checks": check_totals,
    }


def run_live_evaluation(
    cases_path: Path,
    output_path: Path,
    *,
    repetitions: int = 2,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run the fixed dataset against live model and provider APIs."""
    if repetitions < 1:
        raise ValueError("Repetitions must be at least one")
    cases = load_cases(cases_path)
    resolved = settings or get_settings()
    results: list[EvalResult] = []
    with build_persistent_crypto_agent(resolved) as agent:
        for repetition in range(1, repetitions + 1):
            for case in cases:
                config = thread_config(f"eval-{case.id}-{repetition}-{uuid4().hex[:8]}")
                case_messages: list[BaseMessage] = []
                started = time.perf_counter()
                for turn in case.turns:
                    state = agent.graph.invoke(
                        {"messages": [HumanMessage(content=turn)]},
                        config,
                    )
                    case_messages = list(state["messages"])
                elapsed = time.perf_counter() - started
                results.append(
                    score_case(
                        case,
                        case_messages,
                        repetition=repetition,
                        latency_seconds=elapsed,
                        model=resolved.openai_model,
                    )
                )

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": resolved.openai_model,
        "repetitions": repetitions,
        "case_count": len(cases),
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
        "pricing_verified_on": "2026-08-12",
        "summary": _summarize(results),
        "results": [asdict(result) for result in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


__all__ = [
    "EvalCase",
    "EvalResult",
    "estimate_model_cost",
    "load_cases",
    "run_live_evaluation",
    "score_case",
]
