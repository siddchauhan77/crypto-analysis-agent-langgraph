"""Bounded LangGraph model-to-tool reasoning loop."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Self

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from crypto_agent.config import Settings, get_settings
from crypto_agent.memory import create_sqlite_checkpointer
from crypto_agent.prompts import DUPLICATE_TOOL_MESSAGE, SYSTEM_PROMPT, TOOL_LIMIT_MESSAGE
from crypto_agent.state import AgentState, count_tool_calls_since_last_human
from crypto_agent.tools import CryptoToolSet, build_crypto_tool_set

MAX_TOOL_CALLS_PER_TURN = 6
CAUSAL_UNCERTAINTY_TERMS = (
    "cannot confirm",
    "does not establish",
    "doesn't establish",
    "do not establish",
    "not directly evidenced",
    "no direct causation",
    "does not prove",
    "do not prove",
    "hypothesis",
    "speculative",
)


def _tool_call_key(tool_call: dict[str, object]) -> str:
    return json.dumps(
        {"name": tool_call["name"], "args": tool_call["args"]},
        sort_keys=True,
        separators=(",", ":"),
    )


def _latest_tool_calls_repeat_current_turn(state: AgentState) -> bool:
    latest = state["messages"][-1]
    if not isinstance(latest, AIMessage) or not latest.tool_calls:
        return False
    previous: set[str] = set()
    for message in reversed(state["messages"][:-1]):
        if message.type == "human":
            break
        if isinstance(message, AIMessage):
            previous.update(_tool_call_key(call) for call in message.tool_calls)
    return any(_tool_call_key(call) in previous for call in latest.tool_calls)


def _current_turn_tool_evidence(
    messages: Sequence[BaseMessage],
) -> tuple[list[tuple[str, str]], set[str]]:
    latest_human = max(
        (index for index, message in enumerate(messages) if message.type == "human"),
        default=-1,
    )
    call_names: dict[str, str] = {}
    evidence: list[tuple[str, str]] = []
    tool_names: set[str] = set()
    for message in messages[latest_human + 1 :]:
        if isinstance(message, AIMessage):
            call_names.update({call["id"]: call["name"] for call in message.tool_calls})
            continue
        if not isinstance(message, ToolMessage):
            continue
        tool_name = call_names.get(message.tool_call_id)
        if tool_name:
            tool_names.add(tool_name)
        try:
            payload = json.loads(message.content)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        source = payload.get("source")
        retrieved_at = payload.get("retrieved_at")
        if isinstance(source, str) and isinstance(retrieved_at, str):
            pair = (source, retrieved_at)
            if pair not in evidence:
                evidence.append(pair)
    return evidence, tool_names


def _enforce_response_contract(
    messages: Sequence[BaseMessage],
    response: AIMessage,
) -> AIMessage:
    if response.tool_calls:
        return response
    evidence, tool_names = _current_turn_tool_evidence(messages)
    if not evidence:
        return response

    content = response.text
    additions: list[str] = []
    for source, retrieved_at in evidence:
        if source.lower() not in content.lower():
            additions.append(f"Data provider: {source}")
        if retrieved_at not in content:
            additions.append(f"Retrieved: {retrieved_at}")

    combines_market_and_news = {
        "get_crypto_market_data",
        "search_crypto_news",
    }.issubset(tool_names)
    has_causal_caveat = any(term in content.lower() for term in CAUSAL_UNCERTAINTY_TERMS)
    if combines_market_and_news and not has_causal_caveat:
        additions.append("The headlines do not establish what caused the price movement.")

    if not additions:
        return response
    updated = f"{content.rstrip()}\n\n" + "  \n".join(additions)
    return response.model_copy(update={"content": updated})


def build_agent_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compile a model → tools → model loop with optional thread persistence."""
    if max_tool_calls < 1:
        raise ValueError("max_tool_calls must be at least one")

    bound_model: Runnable = model.bind_tools(tools, parallel_tool_calls=False)

    def call_model(state: AgentState) -> dict[str, object]:
        response = bound_model.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        response = _enforce_response_contract(state["messages"], response)
        messages = [*state["messages"], response]
        return {
            "messages": [response],
            "tool_call_count": count_tool_calls_since_last_human(messages),
        }

    def route_after_model(
        state: AgentState,
    ) -> Literal["tools", "duplicate_tool", "tool_limit", "__end__"]:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return END
        if state.get("tool_call_count", 0) > max_tool_calls:
            return "tool_limit"
        if _latest_tool_calls_repeat_current_turn(state):
            return "duplicate_tool"
        return "tools"

    def reject_duplicate_tool(state: AgentState) -> dict[str, object]:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            raise TypeError("Duplicate-tool node requires an AIMessage")
        rejected = [
            ToolMessage(
                content=json.dumps(
                    {
                        "status": "error",
                        "error_type": "duplicate_tool_call",
                        "message": DUPLICATE_TOOL_MESSAGE,
                        "retryable": False,
                    }
                ),
                tool_call_id=tool_call["id"],
            )
            for tool_call in last_message.tool_calls
        ]
        return {"messages": rejected}

    def stop_at_tool_limit(state: AgentState) -> dict[str, object]:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            raise TypeError("Tool-limit node requires an AIMessage")
        rejected = [
            ToolMessage(
                content=json.dumps(
                    {
                        "status": "error",
                        "error_type": "tool_limit",
                        "message": TOOL_LIMIT_MESSAGE,
                        "retryable": False,
                    }
                ),
                tool_call_id=tool_call["id"],
            )
            for tool_call in last_message.tool_calls
        ]
        return {"messages": [*rejected, AIMessage(content=TOOL_LIMIT_MESSAGE)]}

    builder = StateGraph(AgentState)
    builder.add_node("model", call_model)
    builder.add_node(
        "tools",
        ToolNode(
            tools,
            handle_tool_errors=(ValueError, TypeError),
        ),
    )
    builder.add_node("tool_limit", stop_at_tool_limit)
    builder.add_node("duplicate_tool", reject_duplicate_tool)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route_after_model)
    builder.add_edge("tools", "model")
    builder.add_edge("duplicate_tool", "model")
    builder.add_edge("tool_limit", END)
    return builder.compile(checkpointer=checkpointer)


@dataclass
class CryptoAgent:
    """Own the production model, provider tools, and compiled graph."""

    tool_set: CryptoToolSet
    graph: CompiledStateGraph
    checkpointer: SqliteSaver | None = None

    def close(self) -> None:
        self.tool_set.close()
        if self.checkpointer is not None:
            self.checkpointer.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_crypto_agent(settings: Settings | None = None) -> CryptoAgent:
    """Build a stateless production graph from validated local configuration."""
    resolved = settings or get_settings()
    tool_set = build_crypto_tool_set(resolved)
    model = ChatOpenAI(
        model=resolved.openai_model,
        api_key=resolved.openai_api_key,
        temperature=0,
        timeout=resolved.request_timeout_seconds,
        max_retries=resolved.max_http_retries,
        use_responses_api=True,
    )
    return CryptoAgent(
        tool_set=tool_set,
        graph=build_agent_graph(model, tool_set.tools),
    )


def build_persistent_crypto_agent(settings: Settings | None = None) -> CryptoAgent:
    """Build a local SQLite-backed graph for resumable CLI threads."""
    resolved = settings or get_settings()
    tool_set = build_crypto_tool_set(resolved)
    checkpointer = create_sqlite_checkpointer(resolved.checkpoint_db_path)
    model = ChatOpenAI(
        model=resolved.openai_model,
        api_key=resolved.openai_api_key,
        temperature=0,
        timeout=resolved.request_timeout_seconds,
        max_retries=resolved.max_http_retries,
        use_responses_api=True,
    )
    return CryptoAgent(
        tool_set=tool_set,
        graph=build_agent_graph(model, tool_set.tools, checkpointer=checkpointer),
        checkpointer=checkpointer,
    )


__all__ = [
    "MAX_TOOL_CALLS_PER_TURN",
    "CryptoAgent",
    "build_agent_graph",
    "build_crypto_agent",
    "build_persistent_crypto_agent",
]
