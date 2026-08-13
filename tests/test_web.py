"""Public web boundary tests with no live provider or model usage."""

import json
from dataclasses import dataclass
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
                        }
                    ),
                    tool_call_id="call-1",
                ),
                AIMessage(content="Grounded answer from NewsAPI."),
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
    response = TestClient(web.app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "read-only",
        "access_code_required": False,
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
    assert fake_graph.input is not None
    assert len(fake_graph.input["messages"]) == 3  # type: ignore[arg-type]


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
