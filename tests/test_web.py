"""Public web boundary tests with no live provider or model usage."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Self

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from crypto_agent import web


class FakeGraph:
    def __init__(self) -> None:
        self.input: dict[str, object] | None = None

    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.input = payload
        messages = payload["messages"]
        assert isinstance(messages, list)
        return {
            "messages": [
                *messages,
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_crypto_news",
                            "args": {"query": "bitcoin"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content=json.dumps(
                        {
                            "status": "ok",
                            "source": "NewsAPI",
                            "retrieved_at": "2026-08-12T10:00:00Z",
                            "articles": [
                                {"title": "Market update", "url": "https://example.com/news"}
                            ],
                            "api_key": "provider-secret",
                        }
                    ),
                    tool_call_id="call-1",
                ),
                AIMessage(content="Grounded answer from NewsAPI."),
            ]
        }


class FakeMarketGraph:
    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        messages = payload["messages"]
        assert isinstance(messages, list)
        return {
            "messages": [
                *messages,
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_crypto_market_data",
                            "args": {"symbols": ["BTC", "ETH"]},
                            "id": "call-market",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content=json.dumps(
                        {
                            "status": "ok",
                            "source": "FreeCryptoAPI",
                            "retrieved_at": "2026-08-12T10:00:00Z",
                            "items": [
                                {
                                    "symbol": "BTC",
                                    "price_usd": "63500.25",
                                    "change_24h_pct": "1.25",
                                    "high_24h_usd": "64000",
                                    "low_24h_usd": "62000",
                                },
                                {
                                    "symbol": "ETH",
                                    "price_usd": "1875.50",
                                    "change_24h_pct": "-0.45",
                                    "high_24h_usd": "1900",
                                    "low_24h_usd": "1800",
                                },
                            ],
                        }
                    ),
                    tool_call_id="call-market",
                ),
                AIMessage(content="Current comparison."),
            ]
        }


@dataclass
class FakeAgent:
    graph: FakeGraph

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_health_reports_read_only_mode(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    monkeypatch.setattr(web, "BOOTSTRAP_ADMIN_CODE_SHA256", "")
    response = TestClient(web.app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "read-only",
        "access_code_required": False,
        "admin_trace_configured": False,
    }
    assert response.headers["cache-control"] == "no-store"


def test_chat_runs_existing_graph_and_returns_evidence(monkeypatch) -> None:
    fake_graph = FakeGraph()
    monkeypatch.setattr(web, "build_crypto_agent", lambda: FakeAgent(fake_graph))
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)

    response = TestClient(web.app).post(
        "/api/chat",
        json={
            "message": "What changed?",
            "history": [
                {"role": "user", "content": "Show Bitcoin news."},
                {"role": "assistant", "content": "Earlier answer."},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Grounded answer from NewsAPI."
    assert payload["tools_used"] == ["search_crypto_news"]
    assert payload["sources"] == ["NewsAPI"]
    assert payload["retrieved_at"] == ["2026-08-12T10:00:00Z"]
    assert payload["citations"] == [{"label": "Market update", "url": "https://example.com/news"}]
    assert payload["chart"] is None
    assert fake_graph.input is not None
    assert len(fake_graph.input["messages"]) == 3  # type: ignore[arg-type]


def test_chat_returns_current_market_chart(monkeypatch) -> None:
    monkeypatch.setattr(web, "build_crypto_agent", lambda: FakeAgent(FakeMarketGraph()))
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)

    response = TestClient(web.app).post("/api/chat", json={"message": "Compare BTC and ETH."})

    assert response.status_code == 200
    chart = response.json()["chart"]
    assert chart == {
        "kind": "price_comparison",
        "unit": "USD",
        "source": "FreeCryptoAPI",
        "retrieved_at": "2026-08-12T10:00:00Z",
        "points": [
            {
                "symbol": "BTC",
                "price_usd": 63500.25,
                "change_24h_pct": 1.25,
                "high_24h_usd": 64000.0,
                "low_24h_usd": 62000.0,
            },
            {
                "symbol": "ETH",
                "price_usd": 1875.5,
                "change_24h_pct": -0.45,
                "high_24h_usd": 1900.0,
                "low_24h_usd": 1800.0,
            },
        ],
    }


def test_chat_requires_configured_demo_code(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_ACCESS_CODE", "private-demo")
    client = TestClient(web.app)

    denied = client.post("/api/chat", json={"message": "Compare BTC and ETH."})
    assert denied.status_code == 401

    fake_graph = FakeGraph()
    monkeypatch.setattr(web, "build_crypto_agent", lambda: FakeAgent(fake_graph))
    allowed = client.post(
        "/api/chat",
        headers={"X-Demo-Access-Code": "private-demo"},
        json={"message": "Compare BTC and ETH."},
    )
    assert allowed.status_code == 200


def test_admin_chat_is_disabled_without_a_separate_admin_code(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    monkeypatch.setattr(web, "BOOTSTRAP_ADMIN_CODE_SHA256", "")
    response = TestClient(web.app).post(
        "/api/admin/chat",
        headers={"X-Admin-Access-Code": "private-admin"},
        json={"message": "Show Bitcoin news."},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Admin trace is not configured."


def test_admin_session_accepts_the_hashed_bootstrap_code(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    monkeypatch.setattr(
        web,
        "BOOTSTRAP_ADMIN_CODE_SHA256",
        sha256(b"private-admin").hexdigest(),
    )

    response = TestClient(web.app).post(
        "/api/admin/session",
        headers={"X-Admin-Access-Code": "private-admin"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_chat_rejects_the_wrong_admin_role_code(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "private-admin")
    response = TestClient(web.app).post(
        "/api/admin/chat",
        headers={"X-Admin-Access-Code": "wrong-code"},
        json={"message": "Show Bitcoin news."},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin access required."


def test_admin_session_verifies_role_without_running_the_agent(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "private-admin")
    response = TestClient(web.app).post(
        "/api/admin/session",
        headers={"X-Admin-Access-Code": "private-admin"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "role": "admin",
        "capabilities": ["redacted_execution_trace"],
    }


def test_admin_chat_returns_redacted_observable_execution_trace(monkeypatch) -> None:
    fake_graph = FakeGraph()
    monkeypatch.setattr(web, "build_crypto_agent", lambda: FakeAgent(fake_graph))
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "private-admin")

    response = TestClient(web.app).post(
        "/api/admin/chat",
        headers={"X-Admin-Access-Code": "private-admin"},
        json={
            "message": "Show Bitcoin news.",
            "history": [{"role": "assistant", "content": "Earlier answer."}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "admin"
    assert payload["trace_notice"] == (
        "Observable execution metadata only. No hidden chain-of-thought is exposed."
    )
    assert payload["safeguards"] == [
        "Read-only tools",
        "Six tool calls per turn",
        "Duplicate calls rejected",
        "Secrets redacted",
        "No-store response",
    ]
    assert payload["insights"] == [
        {
            "kind": "observed",
            "label": "Routing",
            "value": "1 tool selected: search_crypto_news",
        },
        {
            "kind": "observed",
            "label": "Evidence",
            "value": "1 provider and 1 retrieval timestamp returned",
        },
        {
            "kind": "control",
            "label": "Tool budget",
            "value": "1 of 6 calls used",
        },
        {
            "kind": "boundary",
            "label": "Trace scope",
            "value": "Current request only. No retained production trace.",
        },
    ]
    assert [step["stage"] for step in payload["trace"]] == [
        "request",
        "model",
        "tool",
        "response",
    ]
    assert payload["trace"][0]["input"] == {
        "message": "Show Bitcoin news.",
        "history_messages": 1,
        "message_character_limit": 1200,
        "history_message_limit": 12,
    }
    assert payload["trace"][1]["output"] == {
        "tool_name": "search_crypto_news",
        "arguments": {"query": "bitcoin"},
    }
    assert payload["trace"][2]["output"]["source"] == "NewsAPI"
    assert payload["trace"][2]["output"]["api_key"] == "[REDACTED]"
    assert payload["trace"][3]["output"] == {
        "answer": "Grounded answer from NewsAPI.",
        "sources": ["NewsAPI"],
        "retrieved_at": ["2026-08-12T10:00:00Z"],
    }
    serialized = json.dumps(payload)
    assert "provider-secret" not in serialized
    assert "private-admin" not in serialized
    assert payload["duration_ms"] >= 0


def test_chat_rejects_oversized_prompt() -> None:
    response = TestClient(web.app).post(
        "/api/chat",
        json={"message": "x" * (web.MAX_MESSAGE_CHARACTERS + 1)},
    )
    assert response.status_code == 422


def test_chat_response_does_not_allow_framing(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
    response = TestClient(web.app).get("/api/health")
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
