"""LangGraph state and per-turn tool-call accounting."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Conversation messages plus an observable current-turn tool-call count."""

    tool_call_count: int


def count_tool_calls_since_last_human(messages: list[BaseMessage]) -> int:
    """Count model-requested tool calls in the current user turn."""
    total = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, AIMessage):
            total += len(message.tool_calls)
    return total
