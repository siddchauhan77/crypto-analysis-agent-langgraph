import json
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from crypto_agent.clients import FreeCryptoClient, NewsAPIClient
from crypto_agent.tools import create_crypto_tools

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def tools() -> Iterator[dict[str, BaseTool]]:
    def freecrypto_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getCryptoList"):
            return httpx.Response(200, json=load_fixture("freecrypto_list.json"))
        if request.url.path.endswith("/getData"):
            return httpx.Response(200, json=load_fixture("freecrypto_data.json"))
        raise AssertionError(f"Unexpected FreeCryptoAPI path: {request.url.path}")

    def news_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_fixture("newsapi_everything.json"))

    with ExitStack() as stack:
        freecrypto_client = stack.enter_context(
            FreeCryptoClient("key", transport=httpx.MockTransport(freecrypto_handler))
        )
        newsapi_client = stack.enter_context(
            NewsAPIClient("key", transport=httpx.MockTransport(news_handler))
        )
        created = create_crypto_tools(freecrypto_client, newsapi_client)
        yield {item.name: item for item in created}


def test_registry_has_three_distinct_tools(tools: dict[str, BaseTool]) -> None:
    assert set(tools) == {
        "list_cryptocurrencies",
        "get_crypto_market_data",
        "search_crypto_news",
    }
    assert "verify a symbol" in tools["list_cryptocurrencies"].description
    assert "one to five" in tools["get_crypto_market_data"].description
    assert "headlines" in tools["search_crypto_news"].description


def test_tool_schemas_publish_limits_and_argument_descriptions(
    tools: dict[str, BaseTool],
) -> None:
    market_schema = tools["get_crypto_market_data"].args_schema.model_json_schema()
    news_schema = tools["search_crypto_news"].args_schema.model_json_schema()

    assert market_schema["properties"]["symbols"]["maxItems"] == 5
    assert "One to five" in market_schema["properties"]["symbols"]["description"]
    assert (
        tools["list_cryptocurrencies"].args_schema.model_json_schema()["properties"]["limit"][
            "maximum"
        ]
        == 25
    )
    assert news_schema["properties"]["limit"]["maximum"] == 10
    assert news_schema["properties"]["from_date"]["description"].startswith("Optional")


def test_list_tool_returns_structured_bounded_result(tools: dict[str, BaseTool]) -> None:
    result = tools["list_cryptocurrencies"].invoke({"query": "bit", "limit": 1})

    assert result["status"] == "ok"
    assert result["items"] == [{"symbol": "BTC", "name": "Bitcoin", "provider_source": "binance"}]
    assert result["source"] == "FreeCryptoAPI"
    assert result["retrieved_at"].endswith("Z")


def test_market_tool_normalizes_symbols_and_returns_compact_json(
    tools: dict[str, BaseTool],
) -> None:
    result = tools["get_crypto_market_data"].invoke({"symbols": ["btc", "BTC"]})

    assert result["status"] == "ok"
    assert result["items"][0]["symbol"] == "BTC"
    assert result["items"][0]["price_usd"] == "119500.25"
    assert "market_cap_usd" not in result["items"][0]
    assert result["source"] == "FreeCryptoAPI"


def test_news_tool_accepts_iso_date_and_omits_null_article_fields(
    tools: dict[str, BaseTool],
) -> None:
    result = tools["search_crypto_news"].invoke(
        {"query": "bitcoin", "from_date": "2026-08-01", "limit": 2}
    )

    assert result["status"] == "ok"
    assert len(result["articles"]) == 2
    assert result["articles"][0]["source_name"] == "Example News"
    assert "author" not in result["articles"][1]
    assert result["source"] == "NewsAPI"


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("list_cryptocurrencies", {"limit": 26}),
        ("get_crypto_market_data", {"symbols": []}),
        ("get_crypto_market_data", {"symbols": ["BTC/USD"]}),
        ("search_crypto_news", {"query": "   "}),
        ("search_crypto_news", {"query": "bitcoin", "limit": 11}),
    ],
)
def test_invalid_tool_arguments_fail_before_client_execution(
    tools: dict[str, BaseTool],
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        tools[tool_name].invoke(arguments)


def test_provider_failure_stays_structured_tool_content() -> None:
    def freecrypto_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": "rateLimited"})

    def news_handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("news client should not be called")

    with (
        FreeCryptoClient("key", transport=httpx.MockTransport(freecrypto_handler)) as free,
        NewsAPIClient("key", transport=httpx.MockTransport(news_handler)) as news,
    ):
        tools = {item.name: item for item in create_crypto_tools(free, news)}
        result = tools["get_crypto_market_data"].invoke({"symbols": ["BTC"]})

    assert result["status"] == "error"
    assert result["error_type"] == "rate_limited"
    assert result["retryable"] is True
    assert result["source"] == "FreeCryptoAPI"
    assert result["provider_code"] == "rateLimited"
