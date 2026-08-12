"""NewsAPI client and provider-to-domain normalization."""

import time
from collections.abc import Callable
from datetime import date, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from crypto_agent.clients.base import BaseAPIClient, utc_now
from crypto_agent.models import (
    ErrorType,
    NewsArticle,
    NewsLanguage,
    NewsSearchRequest,
    NewsSearchResponse,
    NewsSearchResult,
    ProviderError,
)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class _RawNewsSource(_ProviderModel):
    id: str | None = None
    name: str


class _RawNewsArticle(_ProviderModel):
    source: _RawNewsSource
    author: str | None = None
    title: str
    description: str | None = None
    url: str
    published_at: datetime | None = Field(default=None, alias="publishedAt")


class _RawNewsResponse(_ProviderModel):
    status: str
    total_results: int = Field(default=0, alias="totalResults")
    articles: list[_RawNewsArticle] = Field(default_factory=list)
    code: str | None = None
    message: str | None = None


class NewsAPIClient(BaseAPIClient):
    BASE_URL = "https://newsapi.org/v2"

    def __init__(
        self,
        api_key: str | SecretStr,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        super().__init__(
            source="NewsAPI",
            base_url=self.BASE_URL,
            headers={
                "X-Api-Key": key,
                "Accept": "application/json",
                "User-Agent": "crypto-analysis-agent/0.1",
            },
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )

    def search_news(
        self,
        query: str,
        *,
        from_date: date | None = None,
        language: NewsLanguage = "en",
        limit: int = 10,
    ) -> NewsSearchResponse:
        try:
            request = NewsSearchRequest(
                query=query,
                from_date=from_date,
                language=language,
                limit=limit,
            )
        except ValidationError:
            return self._error(
                ErrorType.INVALID_INPUT,
                "News search parameters are invalid.",
                retryable=False,
            )

        params: dict[str, str | int] = {
            "q": request.query,
            "language": request.language,
            "sortBy": "publishedAt",
            "pageSize": request.limit,
            "page": 1,
        }
        if request.from_date:
            params["from"] = request.from_date.isoformat()

        payload = self.get_json("/everything", params=params)
        if isinstance(payload, ProviderError):
            return payload
        try:
            raw = _RawNewsResponse.model_validate(payload)
        except ValidationError:
            return self._error(
                ErrorType.UPSTREAM_ERROR,
                "NewsAPI returned a malformed article response.",
                retryable=False,
            )
        if raw.status.casefold() != "ok":
            return self._provider_failure(raw.code)
        if not raw.articles:
            return self._error(
                ErrorType.EMPTY_RESULT,
                "NewsAPI returned no articles for the bounded search.",
                retryable=False,
            )

        articles = [
            NewsArticle(
                title=article.title,
                source_name=article.source.name,
                published_at=article.published_at,
                url=article.url,
                description=article.description,
                author=article.author,
            )
            for article in raw.articles
        ]
        return NewsSearchResult(
            articles=articles,
            total_results=raw.total_results,
            retrieved_at=utc_now(),
        )

    def _provider_failure(self, code: str | None) -> ProviderError:
        if code in {"apiKeyDisabled", "apiKeyInvalid", "apiKeyMissing"}:
            error_type = ErrorType.UNAUTHORIZED
            retryable = False
        elif code in {"apiKeyExhausted", "rateLimited"}:
            error_type = ErrorType.RATE_LIMITED
            retryable = True
        elif code in {
            "parameterInvalid",
            "parametersMissing",
            "sourceDoesNotExist",
            "sourcesTooMany",
        }:
            error_type = ErrorType.INVALID_INPUT
            retryable = False
        else:
            error_type = ErrorType.UPSTREAM_ERROR
            retryable = code == "unexpectedError"
        return self._error(
            error_type,
            "NewsAPI reported an unsuccessful response.",
            retryable=retryable,
            provider_code=code,
        )
