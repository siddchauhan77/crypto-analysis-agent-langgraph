from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from crypto_agent.graph import build_agent_graph
from crypto_agent.memory import (
    create_sqlite_checkpointer,
    get_thread_messages,
    new_thread_id,
    thread_config,
    validate_thread_id,
)


class RecordingMemoryModel(FakeMessagesListChatModel):
    seen_messages: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: list[BaseTool], **kwargs: Any) -> Runnable:
        return self

    def invoke(self, input: list[BaseMessage], config: Any = None, **kwargs: Any) -> BaseMessage:
        self.seen_messages.append(input)
        return super().invoke(input, config, **kwargs)


@tool
def echo_market(symbol: str) -> dict[str, str]:
    """Return a deterministic market-test value."""
    return {"symbol": symbol, "change_24h": "1.0"}


def visible_content(messages: list[BaseMessage]) -> list[str]:
    return [message.text for message in messages]


def test_same_in_memory_thread_includes_previous_turn() -> None:
    model = RecordingMemoryModel(
        responses=[AIMessage(content="BTC moved more."), AIMessage(content="It refers to BTC.")]
    )
    graph = build_agent_graph(model, [echo_market], checkpointer=InMemorySaver())
    config = thread_config("same-thread")

    graph.invoke({"messages": [HumanMessage(content="Compare BTC and ETH")]}, config)
    graph.invoke({"messages": [HumanMessage(content="Which moved more?")]}, config)

    second_turn = visible_content(model.seen_messages[1])
    assert "Compare BTC and ETH" in second_turn
    assert "BTC moved more." in second_turn
    assert "Which moved more?" in second_turn


def test_fresh_thread_is_isolated() -> None:
    model = RecordingMemoryModel(
        responses=[AIMessage(content="First answer."), AIMessage(content="Second answer.")]
    )
    graph = build_agent_graph(model, [echo_market], checkpointer=InMemorySaver())

    graph.invoke(
        {"messages": [HumanMessage(content="Private alpha context")]},
        thread_config("alpha"),
    )
    graph.invoke(
        {"messages": [HumanMessage(content="Independent beta context")]},
        thread_config("beta"),
    )

    second_turn = visible_content(model.seen_messages[1])
    assert "Private alpha context" not in second_turn
    assert "First answer." not in second_turn
    assert "Independent beta context" in second_turn


def test_sqlite_thread_survives_graph_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "checkpoints.sqlite3"
    first_saver = create_sqlite_checkpointer(database_path)
    first_model = RecordingMemoryModel(responses=[AIMessage(content="ETH moved more.")])
    first_graph = build_agent_graph(first_model, [echo_market], checkpointer=first_saver)
    config = thread_config("restart-proof")

    first_graph.invoke({"messages": [HumanMessage(content="Compare BTC and ETH")]}, config)
    first_saver.conn.close()

    second_saver = create_sqlite_checkpointer(database_path)
    second_model = RecordingMemoryModel(responses=[AIMessage(content="ETH was the prior winner.")])
    second_graph = build_agent_graph(second_model, [echo_market], checkpointer=second_saver)
    second_graph.invoke({"messages": [HumanMessage(content="Which moved more?")]}, config)

    second_turn = visible_content(second_model.seen_messages[0])
    assert "Compare BTC and ETH" in second_turn
    assert "ETH moved more." in second_turn
    assert "Which moved more?" in second_turn
    assert len(get_thread_messages(second_graph, "restart-proof")) == 4
    second_saver.conn.close()


@pytest.mark.parametrize("thread_id", ["alpha", "crypto-123", "user_1.test"])
def test_validate_thread_id_accepts_safe_names(thread_id: str) -> None:
    assert validate_thread_id(thread_id) == thread_id


@pytest.mark.parametrize("thread_id", ["", "has spaces", "../escape", "a" * 65])
def test_validate_thread_id_rejects_unsafe_names(thread_id: str) -> None:
    with pytest.raises(ValueError, match="Thread ID"):
        validate_thread_id(thread_id)


def test_new_thread_id_is_safe_and_unique() -> None:
    first = new_thread_id()
    second = new_thread_id()

    assert validate_thread_id(first) == first
    assert first != second
