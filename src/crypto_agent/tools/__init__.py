"""Construction and lifecycle management for the three agent tools."""

from dataclasses import dataclass
from typing import Self

from langchain_core.tools import BaseTool

from crypto_agent.clients import FreeCryptoClient, NewsAPIClient
from crypto_agent.config import Settings, get_settings
from crypto_agent.tools.crypto_list import create_list_cryptocurrencies_tool
from crypto_agent.tools.crypto_news import create_crypto_news_tool
from crypto_agent.tools.market_data import create_market_data_tool


def create_crypto_tools(
    freecrypto_client: FreeCryptoClient,
    newsapi_client: NewsAPIClient,
) -> tuple[BaseTool, BaseTool, BaseTool]:
    """Create the fixed MVP tool registry with explicit client dependencies."""
    return (
        create_list_cryptocurrencies_tool(freecrypto_client),
        create_market_data_tool(freecrypto_client),
        create_crypto_news_tool(newsapi_client),
    )


@dataclass
class CryptoToolSet:
    """Own provider clients and expose their bound LangChain tools."""

    freecrypto_client: FreeCryptoClient
    newsapi_client: NewsAPIClient
    tools: tuple[BaseTool, BaseTool, BaseTool]

    def close(self) -> None:
        self.freecrypto_client.close()
        self.newsapi_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_crypto_tool_set(settings: Settings | None = None) -> CryptoToolSet:
    """Build production clients and tools from validated application settings."""
    resolved = settings or get_settings()
    freecrypto_client = FreeCryptoClient(
        resolved.freecrypto_api_key,
        timeout_seconds=resolved.request_timeout_seconds,
        max_retries=resolved.max_http_retries,
    )
    newsapi_client = NewsAPIClient(
        resolved.news_api_key,
        timeout_seconds=resolved.request_timeout_seconds,
        max_retries=resolved.max_http_retries,
    )
    return CryptoToolSet(
        freecrypto_client=freecrypto_client,
        newsapi_client=newsapi_client,
        tools=create_crypto_tools(freecrypto_client, newsapi_client),
    )


__all__ = ["CryptoToolSet", "build_crypto_tool_set", "create_crypto_tools"]
