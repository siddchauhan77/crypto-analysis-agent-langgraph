"""FreeCryptoAPI client and provider-to-domain normalization."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from crypto_agent.clients.base import BaseAPIClient, utc_now
from crypto_agent.models import (
    CryptoListItem,
    CryptoListRequest,
    CryptoListResponse,
    CryptoListResult,
    CryptoMarketItem,
    ErrorType,
    MarketDataRequest,
    MarketDataResponse,
    MarketDataResult,
    ProviderError,
)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _RawCryptoListItem(_ProviderModel):
    symbol: str
    name: str
    source: str | None = None


class _RawCryptoListResponse(_ProviderModel):
    status: bool
    resultset_size: int = 0
    result: list[_RawCryptoListItem] = Field(default_factory=list)
    error: str | None = None


class _RawMarketItem(_ProviderModel):
    symbol: str
    last: str | None = None
    daily_change_percentage: str | None = None
    highest: str | None = None
    lowest: str | None = None
    last_btc: str | None = None
    source_exchange: str | None = None
    date: str | None = None


class _RawMarketResponse(_ProviderModel):
    status: bool | str
    symbols: list[_RawMarketItem] = Field(default_factory=list)
    error: str | None = None


class FreeCryptoClient(BaseAPIClient):
    BASE_URL = "https://api.freecryptoapi.com/v1"

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
            source="FreeCryptoAPI",
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "User-Agent": "crypto-analysis-agent/0.1",
            },
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )

    def list_cryptocurrencies(
        self,
        query: str | None = None,
        limit: int = 20,
    ) -> CryptoListResponse:
        try:
            request = CryptoListRequest(query=query, limit=limit)
        except ValidationError:
            return self._error(
                ErrorType.INVALID_INPUT,
                "Cryptocurrency list filters are invalid.",
                retryable=False,
            )

        payload = self.get_json("/getCryptoList")
        if isinstance(payload, ProviderError):
            return payload
        try:
            raw = _RawCryptoListResponse.model_validate(payload)
        except ValidationError:
            return self._malformed_response("cryptocurrency list")
        if not raw.status:
            return self._provider_failure(raw.error)

        items = raw.result
        if request.query:
            term = request.query.casefold()
            items = [
                item
                for item in items
                if term in item.symbol.casefold() or term in item.name.casefold()
            ]
        normalized = [
            CryptoListItem(
                symbol=item.symbol.upper(),
                name=item.name,
                provider_source=item.source,
            )
            for item in items[: request.limit]
        ]
        if not normalized:
            return self._error(
                ErrorType.EMPTY_RESULT,
                "FreeCryptoAPI returned no matching cryptocurrencies.",
                retryable=False,
            )
        return CryptoListResult(
            items=normalized,
            total_supported=raw.resultset_size or len(raw.result),
            retrieved_at=utc_now(),
        )

    def get_market_data(self, symbols: list[str]) -> MarketDataResponse:
        try:
            request = MarketDataRequest(symbols=symbols)
        except ValidationError:
            return self._error(
                ErrorType.INVALID_INPUT,
                "One to five valid cryptocurrency symbols are required.",
                retryable=False,
            )

        payload = self.get_json("/getData", params={"symbol": "+".join(request.symbols)})
        if isinstance(payload, ProviderError):
            return payload
        try:
            raw = _RawMarketResponse.model_validate(payload)
        except ValidationError:
            return self._malformed_response("market data")
        if not _is_success(raw.status):
            return self._provider_failure(raw.error)
        if not raw.symbols:
            return self._error(
                ErrorType.EMPTY_RESULT,
                "FreeCryptoAPI returned no market data for the requested symbols.",
                retryable=False,
            )

        items = [
            CryptoMarketItem(
                symbol=item.symbol.upper(),
                price_usd=_to_decimal(item.last),
                change_24h_pct=_to_decimal(item.daily_change_percentage),
                high_24h_usd=_to_decimal(item.highest),
                low_24h_usd=_to_decimal(item.lowest),
                price_btc=_to_decimal(item.last_btc),
                source_exchange=item.source_exchange,
                provider_timestamp=_to_datetime(item.date),
            )
            for item in raw.symbols
        ]
        returned_symbols = {item.symbol for item in items}
        return MarketDataResult(
            items=items,
            retrieved_at=utc_now(),
            missing_symbols=[
                symbol for symbol in request.symbols if symbol not in returned_symbols
            ],
            limitations=[
                "The free /getData endpoint does not provide market capitalization or volume.",
                "Numeric provider fields arrive as strings and are normalized to decimals.",
            ],
        )

    def _provider_failure(self, provider_message: str | None) -> ProviderError:
        message = (provider_message or "").casefold()
        if "access" in message or "upgrade" in message or "unauthor" in message:
            return self._error(
                ErrorType.UNAUTHORIZED,
                "FreeCryptoAPI rejected the configured credentials or plan access.",
                retryable=False,
            )
        return self._error(
            ErrorType.UPSTREAM_ERROR,
            "FreeCryptoAPI reported an unsuccessful response.",
            retryable=False,
        )

    def _malformed_response(self, label: str) -> ProviderError:
        return self._error(
            ErrorType.UPSTREAM_ERROR,
            f"FreeCryptoAPI returned malformed {label}.",
            retryable=False,
        )


def _is_success(status: bool | str) -> bool:
    if status is True:
        return True
    return isinstance(status, str) and status.casefold() in {"ok", "success", "true"}


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _to_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
