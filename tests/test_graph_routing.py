import json
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field

from crypto_agent.clients import FreeCryptoClient, NewsAPIClient
from crypto_agent.graph import MAX_TOOL_CALLS_PER_TURN, build_agent_graph
from crypto_agent.prompts import SYSTEM_PROMPT, TOOL_LIMIT_MESSAGE
from crypto_agent.tools import create_crypto_tools

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingFakeModel(FakeMessagesListChatModel):
    seen_messages: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)
    parallel_tool_calls: bool | None = None

    def bind_tools(
        self,
        tools: tuple[BaseTool, ...],
        **kwargs: Any,
    ) -> Runnable:
        self.bound_tool_names = [item.name for item in tools]
        self.parallel_tool_calls = kwargs.get("parallel_tool_calls")
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen_messages.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def tool_registry() -> Iterator[tuple]:
    def freecrypto_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getCryptoList"):
            return httpx.Response(200, json=load_fixture("freecrypto_list.json"))
        if request.url.path.endswith("/getData"):
            return httpx.Response(200, json=load_fixture("freecrypto_data.json"))
        raise AssertionError(f"Unexpected FreeCryptoAPI path: {request.url.path}")

    def news_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_fixture("newsapi_everything.json"))

    with ExitStack() as stack:
        free = stack.enter_context(
            FreeCryptoClient("key", transport=httpx.MockTransport(freecrypto_handler))
        )
        news = stack.enter_context(
            NewsAPIClient("key", transport=httpx.MockTransport(news_handler))
        )
        yield create_crypto_tools(free, news)


def tool_call(name: str, arguments: dict[str, object], call_id: str) -> dict[str, object]:
    return {"name": name, "args": arguments, "id": call_id, "type": "tool_call"}


def test_greeting_ends_without_tool_call_and_receives_system_prompt(tool_registry: tuple) -> None:
    model = RecordingFakeModel(responses=[AIMessage(content="Hello. Ask me about crypto markets.")])
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": [HumanMessage(content="Hello")]})

    assert result["messages"][-1].content == "Hello. Ask me about crypto markets."
    assert result["tool_call_count"] == 0
    assert isinstance(model.seen_messages[0][0], SystemMessage)
    assert model.seen_messages[0][0].content == SYSTEM_PROMPT
    assert model.parallel_tool_calls is False
    assert model.bound_tool_names == [
        "list_cryptocurrencies",
        "get_crypto_market_data",
        "search_crypto_news",
    ]


@pytest.mark.parametrize(
    ("question", "name", "arguments", "expected_source"),
    [
        (
            "What is the current BTC price?",
            "get_crypto_market_data",
            {"symbols": ["BTC"]},
            "FreeCryptoAPI",
        ),
        (
            "What is the latest Bitcoin news?",
            "search_crypto_news",
            {"query": "bitcoin", "limit": 2},
            "NewsAPI",
        ),
        (
            "Is XYZ a supported symbol?",
            "list_cryptocurrencies",
            {"query": "XYZ", "limit": 5},
            "FreeCryptoAPI",
        ),
    ],
)
def test_graph_executes_selected_tool_and_returns_to_model(
    tool_registry: tuple,
    question: str,
    name: str,
    arguments: dict[str, object],
    expected_source: str,
) -> None:
    model = RecordingFakeModel(
        responses=[
            AIMessage(content="", tool_calls=[tool_call(name, arguments, "call-1")]),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": [HumanMessage(content=question)]})

    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    payload = json.loads(tool_messages[0].content)
    assert payload["source"] == expected_source
    assert payload["retrieved_at"]
    final = result["messages"][-1].content
    assert final.startswith("Grounded answer.")
    assert f"Data provider: {expected_source}" in final
    assert f"Retrieved: {payload['retrieved_at']}" in final
    assert result["tool_call_count"] == 1


def test_graph_adds_causal_caveat_when_market_and_news_are_combined(
    tool_registry: tuple,
) -> None:
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "get_crypto_market_data",
                        {"symbols": ["BTC"]},
                        "market-1",
                    )
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "search_crypto_news",
                        {"query": "bitcoin", "limit": 2},
                        "news-1",
                    )
                ],
            ),
            AIMessage(content="BTC moved while these headlines were published."),
        ]
    )
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke(
        {"messages": [HumanMessage(content="Give BTC movement and recent news context")]}
    )

    final = result["messages"][-1].content
    assert "Data provider: FreeCryptoAPI" in final
    assert "Data provider: NewsAPI" in final
    assert "The headlines do not establish what caused the price movement." in final


def test_comparison_uses_one_multi_symbol_market_call(tool_registry: tuple) -> None:
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "get_crypto_market_data",
                        {"symbols": ["BTC", "ETH"]},
                        "compare-1",
                    )
                ],
            ),
            AIMessage(content="Comparison complete."),
        ]
    )
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": [HumanMessage(content="Compare BTC and ETH")]})

    assert result["tool_call_count"] == 1
    ai_tool_calls = [
        message.tool_calls
        for message in result["messages"]
        if isinstance(message, AIMessage) and message.tool_calls
    ]
    assert ai_tool_calls[0][0]["args"]["symbols"] == ["BTC", "ETH"]


def test_seventh_requested_tool_call_stops_without_provider_execution(
    tool_registry: tuple,
) -> None:
    calls = [
        tool_call("get_crypto_market_data", {"symbols": ["BTC"]}, f"call-{index}")
        for index in range(MAX_TOOL_CALLS_PER_TURN + 1)
    ]
    model = RecordingFakeModel(responses=[AIMessage(content="", tool_calls=calls)])
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": [HumanMessage(content="Make too many calls")]})

    limit_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(limit_messages) == MAX_TOOL_CALLS_PER_TURN + 1
    assert all(
        json.loads(message.content)["error_type"] == "tool_limit" for message in limit_messages
    )
    assert result["messages"][-1].content == TOOL_LIMIT_MESSAGE
    assert result["tool_call_count"] == MAX_TOOL_CALLS_PER_TURN + 1


def test_tool_count_resets_after_latest_human_message(tool_registry: tuple) -> None:
    previous = AIMessage(
        content="",
        tool_calls=[tool_call("get_crypto_market_data", {"symbols": ["BTC"]}, "old-call")],
    )
    history = [
        HumanMessage(content="Old question"),
        previous,
        ToolMessage(content="{}", tool_call_id="old-call"),
        AIMessage(content="Old answer"),
        HumanMessage(content="Hello again"),
    ]
    model = RecordingFakeModel(responses=[AIMessage(content="New answer")])
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": history, "tool_call_count": 1})

    assert result["tool_call_count"] == 0
    assert result["messages"][-1].content == "New answer"


def test_identical_tool_call_is_rejected_before_second_provider_request(
    tool_registry: tuple,
) -> None:
    repeated = tool_call("get_crypto_market_data", {"symbols": ["BTC"]}, "call-1")
    repeated_again = tool_call(
        "get_crypto_market_data",
        {"symbols": ["BTC"]},
        "call-2",
    )
    model = RecordingFakeModel(
        responses=[
            AIMessage(content="", tool_calls=[repeated]),
            AIMessage(content="", tool_calls=[repeated_again]),
            AIMessage(content="Provider result explained."),
        ]
    )
    graph = build_agent_graph(model, tool_registry)

    result = graph.invoke({"messages": [HumanMessage(content="Current BTC price")]})

    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_messages) == 2
    assert json.loads(tool_messages[1].content)["error_type"] == "duplicate_tool_call"
    final = result["messages"][-1].content
    assert final.startswith("Provider result explained.")
    assert "Data provider: FreeCryptoAPI" in final
    assert "Retrieved:" in final
    assert result["tool_call_count"] == 2


def test_graph_exposes_explicit_model_tools_and_limit_nodes(tool_registry: tuple) -> None:
    model = RecordingFakeModel(responses=[AIMessage(content="done")])
    graph = build_agent_graph(model, tool_registry)

    assert {"model", "tools", "duplicate_tool", "tool_limit"}.issubset(graph.get_graph().nodes)
