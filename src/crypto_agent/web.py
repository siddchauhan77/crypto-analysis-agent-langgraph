"""FastAPI boundary for the browser demo."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from hashlib import sha256
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field

from crypto_agent.graph import MAX_TOOL_CALLS_PER_TURN, build_crypto_agent

MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARACTERS = 1_200
REQUESTS_PER_MINUTE = 10
BOOTSTRAP_ADMIN_CODE_SHA256 = "e7670fe7f35f6b4b358a0dabeba0212fd93efbf4c5fc07ca3f43ff188b379e22"


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


class PricePoint(WebModel):
    """One current market observation rendered in the browser chart."""

    symbol: str
    price_usd: float = Field(ge=0)
    change_24h_pct: float | None = None
    high_24h_usd: float | None = Field(default=None, ge=0)
    low_24h_usd: float | None = Field(default=None, ge=0)


class PriceChart(WebModel):
    """A bounded current-price comparison chart sourced from a market tool result."""

    kind: Literal["price_comparison"] = "price_comparison"
    unit: Literal["USD"] = "USD"
    source: str
    retrieved_at: str
    points: list[PricePoint] = Field(min_length=1, max_length=5)


class ChatResponse(WebModel):
    """Browser-facing answer and compact evidence metadata."""

    request_id: str
    answer: str
    tools_used: list[str]
    sources: list[str]
    retrieved_at: list[str]
    citations: list[Citation]
    chart: PriceChart | None = None


class TraceStep(WebModel):
    """One redacted, observable step from the current graph execution."""

    sequence: int
    stage: Literal["request", "model", "tool", "response"]
    label: str
    input: dict[str, object]
    output: dict[str, object]


class TraceInsight(WebModel):
    """One deterministic interpretation of observable execution metadata."""

    kind: Literal["observed", "control", "boundary"]
    label: str
    value: str


class AdminChatResponse(ChatResponse):
    """Standard chat result plus an admin-only observable execution trace."""

    role: Literal["admin"] = "admin"
    duration_ms: int = Field(ge=0)
    trace_notice: str
    safeguards: list[str]
    insights: list[TraceInsight]
    trace: list[TraceStep]


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


def _require_admin_access(access_code: str | None) -> None:
    """Require a separately configured admin code for trace access."""
    expected = os.getenv("ADMIN_ACCESS_CODE", "").strip()
    if expected:
        authorized = secrets.compare_digest(access_code or "", expected)
    elif BOOTSTRAP_ADMIN_CODE_SHA256:
        provided_hash = sha256((access_code or "").encode()).hexdigest()
        authorized = secrets.compare_digest(provided_hash, BOOTSTRAP_ADMIN_CODE_SHA256)
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin trace is not configured.",
        )
    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin access required.",
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
) -> tuple[list[str], list[str], list[str], list[Citation], PriceChart | None]:
    tools: list[str] = []
    sources: list[str] = []
    timestamps: list[str] = []
    citations: list[Citation] = []
    seen_links: set[str] = set()
    chart: PriceChart | None = None

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
        items = result.get("items", [])
        if isinstance(source, str) and isinstance(retrieved_at, str) and isinstance(items, list):
            points: list[PricePoint] = []
            for item in items[:5]:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                price = item.get("price_usd")
                if not isinstance(symbol, str) or not isinstance(price, (str, int, float)):
                    continue
                try:
                    points.append(
                        PricePoint(
                            symbol=symbol[:20],
                            price_usd=float(price),
                            change_24h_pct=(
                                float(item["change_24h_pct"])
                                if item.get("change_24h_pct") is not None
                                else None
                            ),
                            high_24h_usd=(
                                float(item["high_24h_usd"])
                                if item.get("high_24h_usd") is not None
                                else None
                            ),
                            low_24h_usd=(
                                float(item["low_24h_usd"])
                                if item.get("low_24h_usd") is not None
                                else None
                            ),
                        )
                    )
                except (TypeError, ValueError):
                    continue
            if points:
                chart = PriceChart(source=source, retrieved_at=retrieved_at, points=points)
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

    return tools, sources, timestamps, citations, chart


def _invoke_agent(payload: ChatRequest) -> tuple[list[object], AIMessage, int]:
    """Run one bounded graph turn and return observable messages plus duration."""
    started = time.perf_counter()
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

    duration_ms = max(0, round((time.perf_counter() - started) * 1_000))
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
    return messages, final, duration_ms


def _chat_response(messages: list[object], final: AIMessage) -> ChatResponse:
    tools, sources, timestamps, citations, chart = _tool_metadata(messages)
    return ChatResponse(
        request_id=uuid4().hex[:12],
        answer=final.text,
        tools_used=tools,
        sources=sources,
        retrieved_at=timestamps,
        citations=citations,
        chart=chart,
    )


def _redact_trace_value(value: object) -> object:
    """Recursively remove credential-shaped fields and bound trace size."""
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if any(
                marker in normalized
                for marker in (
                    "api_key",
                    "access_code",
                    "authorization",
                    "password",
                    "secret",
                    "token",
                )
            ):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_trace_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_trace_value(item) for item in value[:10]]
    if isinstance(value, tuple):
        return [_redact_trace_value(item) for item in value[:10]]
    if isinstance(value, str):
        return value if len(value) <= 2_000 else f"{value[:2_000]}…[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _execution_trace(
    payload: ChatRequest,
    messages: list[object],
    final: AIMessage,
    response: ChatResponse,
) -> list[TraceStep]:
    """Build a redacted current-turn trace without model chain-of-thought."""
    steps = [
        TraceStep(
            sequence=1,
            stage="request",
            label="Request accepted",
            input={
                "message": payload.message.strip(),
                "history_messages": len(payload.history),
                "message_character_limit": MAX_MESSAGE_CHARACTERS,
                "history_message_limit": MAX_HISTORY_MESSAGES,
            },
            output={"accepted": True},
        )
    ]
    call_names: dict[str, str] = {}
    request_message_count = len(payload.history) + 1
    for message in messages[request_message_count:]:
        if isinstance(message, AIMessage) and message.tool_calls:
            for call in message.tool_calls:
                call_id = str(call.get("id", ""))
                tool_name = str(call.get("name", "unknown"))
                call_names[call_id] = tool_name
                steps.append(
                    TraceStep(
                        sequence=len(steps) + 1,
                        stage="model",
                        label=f"Tool selected: {tool_name}",
                        input={"visible_message_count": request_message_count},
                        output={
                            "tool_name": tool_name,
                            "arguments": _redact_trace_value(call.get("args", {})),
                        },
                    )
                )
            continue
        if isinstance(message, ToolMessage):
            try:
                parsed = json.loads(message.content) if isinstance(message.content, str) else {}
            except json.JSONDecodeError:
                parsed = {"status": "unparseable_tool_output"}
            tool_name = call_names.get(message.tool_call_id, "unknown")
            steps.append(
                TraceStep(
                    sequence=len(steps) + 1,
                    stage="tool",
                    label=f"Tool returned: {tool_name}",
                    input={"tool_name": tool_name, "tool_call_id": message.tool_call_id},
                    output=_redact_trace_value(parsed),
                )
            )

    steps.append(
        TraceStep(
            sequence=len(steps) + 1,
            stage="response",
            label="Grounded answer returned",
            input={"tool_count": len(response.tools_used)},
            output={
                "answer": final.text,
                "sources": response.sources,
                "retrieved_at": response.retrieved_at,
            },
        )
    )
    return steps


def _trace_insights(response: ChatResponse) -> list[TraceInsight]:
    """Explain observed signals without implying provider truth or production reliability."""
    tool_count = len(response.tools_used)
    provider_count = len(response.sources)
    timestamp_count = len(response.retrieved_at)
    tool_label = ", ".join(response.tools_used) if response.tools_used else "none"
    tool_word = "tool" if tool_count == 1 else "tools"
    provider_word = "provider" if provider_count == 1 else "providers"
    timestamp_word = "timestamp" if timestamp_count == 1 else "timestamps"
    return [
        TraceInsight(
            kind="observed",
            label="Routing",
            value=f"{tool_count} {tool_word} selected: {tool_label}",
        ),
        TraceInsight(
            kind="observed",
            label="Evidence",
            value=(
                f"{provider_count} {provider_word} and {timestamp_count} "
                f"retrieval {timestamp_word} returned"
            ),
        ),
        TraceInsight(
            kind="control",
            label="Tool budget",
            value=f"{tool_count} of {MAX_TOOL_CALLS_PER_TURN} calls used",
        ),
        TraceInsight(
            kind="boundary",
            label="Trace scope",
            value="Current request only. No retained production trace.",
        ),
    ]


@app.get("/api/health")
def health() -> dict[str, object]:
    """Return non-sensitive deployment status."""
    return {
        "status": "ok",
        "mode": "read-only",
        "access_code_required": bool(os.getenv("DEMO_ACCESS_CODE", "").strip()),
        "admin_trace_configured": bool(
            os.getenv("ADMIN_ACCESS_CODE", "").strip() or BOOTSTRAP_ADMIN_CODE_SHA256
        ),
    }


@app.post("/api/admin/session")
def admin_session(
    x_admin_access_code: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Verify the admin role without running the model or provider tools."""
    _require_admin_access(x_admin_access_code)
    return {"role": "admin", "capabilities": ["redacted_execution_trace"]}


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    x_demo_access_code: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    """Run one stateless, history-aware turn through the existing LangGraph agent."""
    _require_demo_access(x_demo_access_code)
    _enforce_rate_limit(request)
    messages, final, _ = _invoke_agent(payload)
    return _chat_response(messages, final)


@app.post("/api/admin/chat", response_model=AdminChatResponse)
def admin_chat(
    payload: ChatRequest,
    request: Request,
    x_admin_access_code: Annotated[str | None, Header()] = None,
) -> AdminChatResponse:
    """Run one turn and return a redacted trace to an authorized admin."""
    _require_admin_access(x_admin_access_code)
    _enforce_rate_limit(request)
    messages, final, duration_ms = _invoke_agent(payload)
    response = _chat_response(messages, final)
    return AdminChatResponse(
        **response.model_dump(),
        duration_ms=duration_ms,
        trace_notice="Observable execution metadata only. No hidden chain-of-thought is exposed.",
        safeguards=[
            "Read-only tools",
            "Six tool calls per turn",
            "Duplicate calls rejected",
            "Secrets redacted",
            "No-store response",
        ],
        insights=_trace_insights(response),
        trace=_execution_trace(payload, messages, final, response),
    )
