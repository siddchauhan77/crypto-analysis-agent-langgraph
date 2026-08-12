import json
from datetime import date
from pathlib import Path

import httpx

from crypto_agent.clients import NewsAPIClient
from crypto_agent.models import ErrorType, NewsSearchResult, ProviderError

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture() -> dict[str, object]:
    return json.loads((FIXTURES / "newsapi_everything.json").read_text())


def test_news_search_uses_header_auth_and_bounded_parameters() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=load_fixture())

    with NewsAPIClient("test-news-key", transport=httpx.MockTransport(handler)) as client:
        result = client.search_news(
            "bitcoin OR ethereum",
            from_date=date(2026, 8, 1),
            limit=2,
        )

    assert isinstance(result, NewsSearchResult)
    assert len(result.articles) == 2
    request = captured[0]
    assert request.headers["x-api-key"] == "test-news-key"
    assert "test-news-key" not in str(request.url)
    assert request.url.params["pageSize"] == "2"
    assert request.url.params["from"] == "2026-08-01"


def test_blank_news_query_returns_typed_error_without_network_call() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid input must not reach the provider")

    with NewsAPIClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.search_news("   ")

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.INVALID_INPUT


def test_newsapi_error_code_maps_to_stable_error_type() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "error",
                "code": "apiKeyExhausted",
                "message": "quota reached",
            },
        )

    with NewsAPIClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.search_news("bitcoin")

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.RATE_LIMITED
    assert result.provider_code == "apiKeyExhausted"
    assert "quota reached" not in result.message


def test_empty_news_result_is_distinct_from_provider_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "ok", "totalResults": 0, "articles": []},
        )

    with NewsAPIClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.search_news("unknown bounded query")

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.EMPTY_RESULT
    assert result.retryable is False


def test_http_auth_error_does_not_echo_provider_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"status": "error", "code": "apiKeyInvalid", "message": "secret body"},
        )

    with NewsAPIClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.search_news("bitcoin")

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.UNAUTHORIZED
    assert result.http_status == 401
    assert "secret body" not in result.message


def test_timeout_is_bounded_and_typed() -> None:
    attempts = 0
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    with NewsAPIClient(
        "key",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleep=waits.append,
    ) as client:
        result = client.search_news("bitcoin")

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.TIMEOUT
    assert result.retryable is True
    assert attempts == 2
    assert waits == [0.25]
