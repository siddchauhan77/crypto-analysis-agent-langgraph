"""LangChain tool for current cryptocurrency market data."""

from typing import Any

from langchain.tools import tool
from langchain_core.tools import BaseTool

from crypto_agent.clients import FreeCryptoClient
from crypto_agent.models import MarketDataRequest
from crypto_agent.tools._shared import compact_result


def create_market_data_tool(client: FreeCryptoClient) -> BaseTool:
    """Create a current-market-data tool bound to one API client."""

    @tool(
        "get_crypto_market_data",
        args_schema=MarketDataRequest,
        description=(
            "Fetch current price, 24-hour percentage change, daily high, and daily low for "
            "one to five known cryptocurrency symbols. Use one call for comparisons. "
            "This free endpoint does not provide market cap or volume. Do not use it for news."
        ),
    )
    def get_crypto_market_data(symbols: list[str]) -> dict[str, Any]:
        return compact_result(client.get_market_data(symbols))

    return get_crypto_market_data
