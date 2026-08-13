"""FastAPI boundary for the browser demo."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field

from crypto_agent.graph import build_crypto_agent

MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARACTERS = 1_200
REQUESTS_PER_MINUTE = 10


class WebModel(BaseModel):
    """Reject undocumented fields at the public web boundary."""

    model_config = ConfigDict(extra="forbid")


class VisibleMessage(WebModel):
    """One browser-visible conversation message."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=5_000)


class ChatRequest(WebModel):
    """One bounded browser turn plus visible conversation context."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARACTERS)
    history: list[VisibleMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


class Citation(WebModel):
    """A safe external source link extracted from a tool result."""

    label: str
    url: str


class ChatResponse(WebModel):
    """Browser-facing answer and compact evidence metadata."""

    request_id: str
    answer: str
    tools_used: list[str]
    sources: list[str]
    retrieved_at: list[str]
    citations: list[Citation]


_request_times: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()

app = FastAPI(
    title="Crypto Market Analysis Agent",
    description="Read-only, source-grounded cryptocurrency research.",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Apply browser security and privacy headers to every response."""
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    forwarded_ip = forwarded.split(",", maxsplit=1)[0].strip()
    if forwarded_ip:
        return forwarded_ip
    if request.client:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(request: Request) -> None:
    """Apply a best-effort per-instance request limit for the public demo."""
    now = time.monotonic()
    cutoff = now - 60
    key = _client_key(request)
    with _rate_lock:
        recent = _request_times[key]
        while recent and recent[0] < cutoff:
            recent.popleft()
        if len(recent) >= REQUESTS_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demo limit reached. Wait one minute and try again.",
            )
        recent.append(now)


def _require_demo_access(access_code: str | None) -> None:
    """Require the shared demo code whenever the server is configured with one."""
    expected = os.getenv("DEMO_ACCESS_CODE", "").strip()
    if expected and not secrets.compare_digest(access_code or "", expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Enter the demo access code to use the live agent.",
        )


def _langchain_messages(payload: ChatRequest) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for item in payload.history:
        message_type = HumanMessage if item.role == "user" else AIMessage
        messages.append(message_type(content=item.content.strip()))
    messages.append(HumanMessage(content=payload.message.strip()))
    return messages


def _tool_metadata(
    messages: list[object],
) -> tuple[list[str], list[str], list[str], list[Citation]]:
    tools: list[str] = []
    sources: list[str] = []
    timestamps: list[str] = []
    citations: list[Citation] = []
    seen_links: set[str] = set()

    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                name = str(call.get("name", ""))
                if name and name not in tools:
                    tools.append(name)
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        try:
            result = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if not isinstance(result, dict):
            continue
        source = result.get("source")
        if isinstance(source, str) and source not in sources:
            sources.append(source)
        retrieved_at = result.get("retrieved_at")
        if isinstance(retrieved_at, str) and retrieved_at not in timestamps:
            timestamps.append(retrieved_at)
        articles = result.get("articles", [])
        if not isinstance(articles, list):
            continue
        for article in articles:
            if not isinstance(article, dict):
                continue
            url = article.get("url")
            title = article.get("title")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue
            if url in seen_links or len(citations) >= 6:
                continue
            seen_links.add(url)
            citations.append(Citation(label=str(title or "News source")[:120], url=url))

    return tools, sources, timestamps, citations


@app.get("/api/health")
def health() -> dict[str, object]:
    """Return non-sensitive deployment status."""
    return {
        "status": "ok",
        "mode": "read-only",
        "access_code_required": bool(os.getenv("DEMO_ACCESS_CODE", "").strip()),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    x_demo_access_code: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    """Run one stateless, history-aware turn through the existing LangGraph agent."""
    _require_demo_access(x_demo_access_code)
    _enforce_rate_limit(request)

    try:
        with build_crypto_agent() as agent:
            result = agent.graph.invoke({"messages": _langchain_messages(payload)})
    except Exception as exc:
        error_name = type(exc).__name__
        print(f"crypto-agent request failed: {error_name}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The live analysis request failed. Try again shortly.",
        ) from None

    messages = list(result.get("messages", []))
    final = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, AIMessage) and not message.tool_calls and message.text
        ),
        None,
    )
    if final is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent returned no final answer.",
        )

    tools, sources, timestamps, citations = _tool_metadata(messages)
    return ChatResponse(
        request_id=uuid4().hex[:12],
        answer=final.text,
        tools_used=tools,
        sources=sources,
        retrieved_at=timestamps,
        citations=citations,
    )
