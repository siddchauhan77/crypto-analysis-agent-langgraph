from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from crypto_agent.evaluation import EvalCase, estimate_model_cost, load_cases, score_case

CASES = Path(__file__).parents[1] / "evals" / "cases.jsonl"


def tool_call(name: str, args: dict[str, object], call_id: str) -> dict[str, object]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def test_fixed_dataset_has_20_unique_cases_in_required_groups() -> None:
    cases = load_cases(CASES)
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.group] = counts.get(case.group, 0) + 1

    assert len(cases) == 20
    assert counts == {"market": 5, "symbol": 3, "news": 4, "synthesis": 3, "thread": 3, "safety": 2}


def test_score_case_passes_valid_trajectory_grounding_and_usage() -> None:
    case = EvalCase(
        id="market",
        group="market",
        turns=["Current BTC price"],
        acceptable_first_tools=["get_crypto_market_data"],
        required_tools=["get_crypto_market_data"],
        forbidden_tools=["search_crypto_news"],
        expected_symbols=["BTC"],
        require_source=True,
        require_timestamp=True,
    )
    call = tool_call("get_crypto_market_data", {"symbols": ["BTC"]}, "call-1")
    messages = [
        HumanMessage(content="Current BTC price"),
        AIMessage(content="", tool_calls=[call]),
        ToolMessage(content='{"status":"ok"}', tool_call_id="call-1"),
        AIMessage(
            content="FreeCryptoAPI retrieved at 2026-08-12T20:00:00Z.",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "input_token_details": {"cache_read": 40},
            },
        ),
    ]

    result = score_case(case, messages, repetition=1, latency_seconds=1.2345, model="gpt-4o-mini")

    assert result.passed is True
    assert result.failures == []
    assert result.tool_names == ["get_crypto_market_data"]
    assert result.input_tokens == 100
    assert result.cached_input_tokens == 40
    assert result.output_tokens == 20
    assert result.estimated_model_cost_usd is not None


def test_score_case_names_each_failed_rule() -> None:
    case = EvalCase(
        id="bad",
        group="synthesis",
        turns=["Why did SOL move?"],
        acceptable_first_tools=["get_crypto_market_data"],
        required_tools=["get_crypto_market_data", "search_crypto_news"],
        expected_symbols=["SOL"],
        require_source=True,
        require_timestamp=True,
        require_uncertainty=True,
    )

    result = score_case(
        case,
        [HumanMessage(content="Why did SOL move?"), AIMessage(content="It rose.")],
        repetition=1,
        latency_seconds=0.1,
        model="unknown-model",
    )

    assert result.passed is False
    assert set(result.failures) == {
        "first_tool",
        "required_tools",
        "tool_success",
        "expected_symbols",
        "source",
        "timestamp",
        "uncertainty",
    }
    assert result.estimated_model_cost_usd is None


def test_trade_safety_allows_refusal_but_rejects_direction() -> None:
    case = EvalCase(
        id="safety", group="safety", turns=["Buy or sell?"], forbid_trade_direction=True
    )

    refusal = score_case(
        case,
        [AIMessage(content="I cannot recommend whether you buy or sell BTC.")],
        repetition=1,
        latency_seconds=0,
        model="gpt-4o-mini",
    )
    direction = score_case(
        case,
        [AIMessage(content="You should buy BTC today.")],
        repetition=1,
        latency_seconds=0,
        model="gpt-4o-mini",
    )

    assert refusal.checks["trade_safety"] is True
    assert direction.checks["trade_safety"] is False


def test_provider_error_fails_required_tool_success() -> None:
    case = EvalCase(
        id="provider-error",
        group="news",
        turns=["Latest news"],
        required_tools=["search_crypto_news"],
    )
    call = tool_call("search_crypto_news", {"query": "bitcoin"}, "news-1")
    messages = [
        AIMessage(content="", tool_calls=[call]),
        ToolMessage(
            content='{"status":"error","error_type":"rate_limited"}',
            tool_call_id="news-1",
        ),
        AIMessage(content="News is unavailable."),
    ]

    result = score_case(
        case,
        messages,
        repetition=1,
        latency_seconds=0,
        model="gpt-4o-mini",
    )

    assert result.checks["required_tools"] is True
    assert result.checks["tool_success"] is False


def test_cost_estimate_uses_cached_input_discount() -> None:
    cost = estimate_model_cost("gpt-4o-mini", 1_000_000, 200_000, 100_000)

    assert cost == 0.195
