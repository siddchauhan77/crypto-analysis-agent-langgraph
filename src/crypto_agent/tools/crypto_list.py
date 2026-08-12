"""LangChain tool for supported cryptocurrency discovery."""

from typing import Any

from langchain.tools import tool
from langchain_core.tools import BaseTool

from crypto_agent.clients import FreeCryptoClient
from crypto_agent.models import CryptoListRequest
from crypto_agent.tools._shared import compact_result


def create_list_cryptocurrencies_tool(client: FreeCryptoClient) -> BaseTool:
    """Create a supported-symbol discovery tool bound to one API client."""

    @tool(
        "list_cryptocurrencies",
        args_schema=CryptoListRequest,
        description=(
            "Find cryptocurrency symbols supported by FreeCryptoAPI and provider names when "
            "available. Use this to verify a symbol or search an unknown ticker before market "
            "data. Provider names may be missing, so do not rely on this tool to resolve every "
            "plain-language coin name. Do not use it for prices or news."
        ),
    )
    def list_cryptocurrencies(
        query: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return compact_result(client.list_cryptocurrencies(query=query, limit=limit))

    return list_cryptocurrencies
