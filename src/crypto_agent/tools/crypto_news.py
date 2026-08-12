"""LangChain tool for bounded cryptocurrency news searches."""

from datetime import date
from typing import Any

from langchain.tools import tool
from langchain_core.tools import BaseTool

from crypto_agent.clients import NewsAPIClient
from crypto_agent.models import NewsLanguage, NewsSearchRequest
from crypto_agent.tools._shared import compact_result


def create_crypto_news_tool(client: NewsAPIClient) -> BaseTool:
    """Create a recent-news tool bound to one API client."""

    @tool(
        "search_crypto_news",
        args_schema=NewsSearchRequest,
        description=(
            "Search recent cryptocurrency headlines and truncated snippets by keyword. "
            "Use for news, events, regulation, sentiment, or possible context for a market move. "
            "Results are not full articles and do not prove what caused a price change."
        ),
    )
    def search_crypto_news(
        query: str,
        from_date: date | None = None,
        language: NewsLanguage = "en",
        limit: int = 10,
    ) -> dict[str, Any]:
        return compact_result(
            client.search_news(
                query,
                from_date=from_date,
                language=language,
                limit=limit,
            )
        )

    return search_crypto_news
