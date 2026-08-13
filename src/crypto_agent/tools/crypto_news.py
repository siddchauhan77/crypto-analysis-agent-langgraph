"""LangChain tool for bounded cryptocurrency news searches."""

from typing import Any

from langchain.tools import tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_agent.clients import NewsAPIClient
from crypto_agent.models import NewsLanguage
from crypto_agent.tools._shared import compact_result


class NewsToolRequest(BaseModel):
    """Model-facing recent-news arguments without historical date controls."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=500,
        description="Recent-news search expression, such as bitcoin OR BTC.",
    )
    language: NewsLanguage = Field(
        default="en",
        description="Two-letter language code for returned articles.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of recent headlines and snippets to return.",
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("News query cannot be blank")
        return normalized


def create_crypto_news_tool(client: NewsAPIClient) -> BaseTool:
    """Create a recent-news tool bound to one API client."""

    @tool(
        "search_crypto_news",
        args_schema=NewsToolRequest,
        description=(
            "Search recent cryptocurrency headlines and truncated snippets by keyword. "
            "Use for news, events, regulation, sentiment, or possible context for a market move. "
            "Results are not full articles and do not prove what caused a price change."
        ),
    )
    def search_crypto_news(
        query: str,
        language: NewsLanguage = "en",
        limit: int = 10,
    ) -> dict[str, Any]:
        return compact_result(
            client.search_news(
                query,
                language=language,
                limit=limit,
            )
        )

    return search_crypto_news
