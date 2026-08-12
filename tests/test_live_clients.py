import os

import pytest

from crypto_agent.clients import FreeCryptoClient, NewsAPIClient
from crypto_agent.config import get_settings
from crypto_agent.models import MarketDataResult, NewsSearchResult

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def require_live_opt_in() -> None:
    if os.getenv("RUN_LIVE_API_TESTS") != "1":
        pytest.skip("set RUN_LIVE_API_TESTS=1 to consume provider quota")


def test_live_freecrypto_market_data() -> None:
    settings = get_settings()
    with FreeCryptoClient(
        settings.freecrypto_api_key,
        timeout_seconds=settings.request_timeout_seconds,
        max_retries=settings.max_http_retries,
    ) as client:
        result = client.get_market_data(["BTC"])

    assert isinstance(result, MarketDataResult), result.model_dump_json()
    assert result.items[0].symbol == "BTC"
    assert result.items[0].price_usd is not None


def test_live_news_search() -> None:
    settings = get_settings()
    with NewsAPIClient(
        settings.news_api_key,
        timeout_seconds=settings.request_timeout_seconds,
        max_retries=settings.max_http_retries,
    ) as client:
        result = client.search_news("bitcoin", limit=1)

    assert isinstance(result, NewsSearchResult), result.model_dump_json()
    assert len(result.articles) == 1
