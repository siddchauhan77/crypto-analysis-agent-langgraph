"""Thread identifiers and local SQLite checkpoint construction."""

import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

THREAD_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def new_thread_id() -> str:
    """Create a readable, collision-resistant local thread identifier."""
    return f"crypto-{uuid4().hex[:12]}"


def validate_thread_id(thread_id: str) -> str:
    """Normalize and validate a user-supplied checkpoint namespace."""
    normalized = thread_id.strip()
    if not THREAD_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Thread ID must be 1-64 characters using letters, numbers, dot, underscore, or dash."
        )
    return normalized


def thread_config(thread_id: str) -> RunnableConfig:
    """Build the LangGraph runtime configuration for one isolated thread."""
    return {
        "configurable": {"thread_id": validate_thread_id(thread_id)},
        "metadata": {"session_type": "cli"},
    }


def create_sqlite_checkpointer(path: Path) -> SqliteSaver:
    """Open a lightweight local checkpointer with strict safe-type deserialization."""
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, check_same_thread=False)
    serializer = JsonPlusSerializer(allowed_msgpack_modules=None)
    return SqliteSaver(connection, serde=serializer)


def get_thread_messages(
    graph: CompiledStateGraph,
    thread_id: str,
) -> list[BaseMessage]:
    """Read the latest persisted messages for one thread."""
    snapshot = graph.get_state(thread_config(thread_id))
    messages: Any = snapshot.values.get("messages", [])
    return list(messages)
