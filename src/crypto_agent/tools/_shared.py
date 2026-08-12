"""Shared helpers for compact, structured LangChain tool results."""

from typing import Any

from pydantic import BaseModel


def compact_result(result: BaseModel) -> dict[str, Any]:
    """Convert a validated domain result into JSON-safe tool content."""
    return result.model_dump(mode="json", exclude_none=True)
