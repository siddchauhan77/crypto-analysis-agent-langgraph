import json
from decimal import Decimal
from pathlib import Path

import httpx

from crypto_agent.clients import FreeCryptoClient
from crypto_agent.models import ErrorType, MarketDataResult, ProviderError

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())


def test_list_cryptocurrencies_filters_and_keeps_key_out_of_url() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=load_fixture("freecrypto_list.json"))

    with FreeCryptoClient(
        "test-freecrypto-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.list_cryptocurrencies(query="bit", limit=1)

    assert result.status == "ok"
    assert result.items[0].symbol == "BTC"
    assert result.total_supported == 3821
    assert captured[0].headers["authorization"] == "Bearer test-freecrypto-key"
    assert "test-freecrypto-key" not in str(captured[0].url)


def test_market_data_normalizes_decimals_and_reports_missing_symbols() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTC+ETH"
        return httpx.Response(200, json=load_fixture("freecrypto_data.json"))

    with FreeCryptoClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.get_market_data(["btc", "ETH"])

    assert isinstance(result, MarketDataResult)
    assert result.items[0].price_usd == Decimal("119500.25")
    assert result.items[0].change_24h_pct == Decimal("2.50")
    assert result.missing_symbols == ["ETH"]


def test_blank_provider_name_normalizes_to_missing_data() -> None:
    payload = load_fixture("freecrypto_list.json")
    payload["result"][0]["name"] = ""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with FreeCryptoClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.list_cryptocurrencies(limit=1)

    assert result.status == "ok"
    assert result.items[0].name is None


def test_invalid_symbols_return_typed_error_without_network_call() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid input must not reach the provider")

    with FreeCryptoClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.get_market_data(["BTC/USD"])

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.INVALID_INPUT
    assert result.retryable is False


def test_provider_plan_failure_in_http_200_is_not_treated_as_success() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": False, "error": "No access. Please upgrade your subscription"},
        )

    with FreeCryptoClient("key", transport=httpx.MockTransport(handler)) as client:
        result = client.get_market_data(["BTC"])

    assert isinstance(result, ProviderError)
    assert result.error_type is ErrorType.UNAUTHORIZED


def test_transient_server_error_retries_once() -> None:
    attempts = 0
    waits: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=load_fixture("freecrypto_data.json"))

    with FreeCryptoClient(
        "key",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleep=waits.append,
    ) as client:
        result = client.get_market_data(["BTC"])

    assert isinstance(result, MarketDataResult)
    assert attempts == 2
    assert waits == [0.25]
