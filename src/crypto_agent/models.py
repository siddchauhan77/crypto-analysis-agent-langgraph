"""Stable internal request, response, and error contracts."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    """Reject undocumented fields at internal contract boundaries."""

    model_config = ConfigDict(extra="forbid")


class ErrorType(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UPSTREAM_ERROR = "upstream_error"
    EMPTY_RESULT = "empty_result"


class ProviderError(ContractModel):
    status: Literal["error"] = "error"
    error_type: ErrorType
    message: str
    retryable: bool
    source: str
    retrieved_at: datetime
    http_status: int | None = None
    provider_code: str | None = None


class CryptoListRequest(ContractModel):
    query: str | None = Field(
        default=None,
        max_length=100,
        description="Optional partial symbol or provider name, such as BTC.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=25,
        description="Maximum number of matching cryptocurrencies to return.",
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class MarketDataRequest(ContractModel):
    symbols: list[str] = Field(
        min_length=1,
        max_length=5,
        description="One to five cryptocurrency symbols, such as BTC or ETH.",
    )

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            symbol = value.strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,19}", symbol):
                raise ValueError(f"Invalid cryptocurrency symbol: {value!r}")
            if symbol not in normalized:
                normalized.append(symbol)
        if not normalized:
            raise ValueError("At least one cryptocurrency symbol is required")
        return normalized


NewsLanguage: TypeAlias = Literal[
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "he",
    "it",
    "nl",
    "no",
    "pt",
    "ru",
    "sv",
    "ud",
    "zh",
]


class NewsSearchRequest(ContractModel):
    query: str = Field(
        min_length=1,
        max_length=500,
        description="NewsAPI search expression, such as bitcoin OR BTC.",
    )
    from_date: date | None = Field(
        default=None,
        description="Optional earliest publication date in YYYY-MM-DD format.",
    )
    language: NewsLanguage = Field(
        default="en",
        description="Two-letter language code for returned articles.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of article headlines and snippets to return.",
    )

    @field_validator("query")
    @classmethod
    def normalize_news_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("News query cannot be blank")
        return normalized


class CryptoListItem(ContractModel):
    symbol: str
    name: str | None = None
    provider_source: str | None = None


class CryptoListResult(ContractModel):
    status: Literal["ok"] = "ok"
    items: list[CryptoListItem]
    total_supported: int
    source: Literal["FreeCryptoAPI"] = "FreeCryptoAPI"
    retrieved_at: datetime


class CryptoMarketItem(ContractModel):
    symbol: str
    price_usd: Decimal | None = None
    change_24h_pct: Decimal | None = None
    high_24h_usd: Decimal | None = None
    low_24h_usd: Decimal | None = None
    price_btc: Decimal | None = None
    source_exchange: str | None = None
    provider_timestamp: datetime | None = None


class MarketDataResult(ContractModel):
    status: Literal["ok"] = "ok"
    items: list[CryptoMarketItem]
    source: Literal["FreeCryptoAPI"] = "FreeCryptoAPI"
    provider_endpoint: Literal["/getData"] = "/getData"
    retrieved_at: datetime
    missing_symbols: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class NewsArticle(ContractModel):
    title: str
    source_name: str
    published_at: datetime | None = None
    url: str
    description: str | None = None
    author: str | None = None


class NewsSearchResult(ContractModel):
    status: Literal["ok"] = "ok"
    articles: list[NewsArticle]
    total_results: int
    source: Literal["NewsAPI"] = "NewsAPI"
    retrieved_at: datetime
    limitations: list[str] = Field(
        default_factory=lambda: [
            "NewsAPI results contain headlines and truncated snippets, not full articles.",
            "NewsAPI Developer plan results have a 24-hour publication delay.",
        ]
    )


CryptoListResponse: TypeAlias = CryptoListResult | ProviderError
MarketDataResponse: TypeAlias = MarketDataResult | ProviderError
NewsSearchResponse: TypeAlias = NewsSearchResult | ProviderError
