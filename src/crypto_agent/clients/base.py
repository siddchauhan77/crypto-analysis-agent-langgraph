"""Shared HTTP behavior for external data providers."""

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from crypto_agent.models import ErrorType, ProviderError


def utc_now() -> datetime:
    return datetime.now(UTC)


class BaseAPIClient:
    """HTTP GET client with safe errors and bounded transient retries."""

    def __init__(
        self,
        *,
        source: str,
        base_url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_retries: int,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source = source
        self.max_retries = max_retries
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            headers=dict(headers),
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BaseAPIClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any] | ProviderError:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                return self._error(
                    ErrorType.TIMEOUT,
                    f"{self.source} timed out after bounded retries.",
                    retryable=True,
                )
            except httpx.RequestError:
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                return self._error(
                    ErrorType.UPSTREAM_ERROR,
                    f"{self.source} could not be reached after bounded retries.",
                    retryable=True,
                )

            if response.status_code >= 500 and attempt < self.max_retries:
                self._backoff(attempt)
                continue

            if 200 <= response.status_code < 300:
                try:
                    payload = response.json()
                except ValueError:
                    return self._error(
                        ErrorType.UPSTREAM_ERROR,
                        f"{self.source} returned malformed JSON.",
                        retryable=False,
                        http_status=response.status_code,
                    )
                if not isinstance(payload, dict):
                    return self._error(
                        ErrorType.UPSTREAM_ERROR,
                        f"{self.source} returned an unexpected response shape.",
                        retryable=False,
                        http_status=response.status_code,
                    )
                return payload

            return self._http_error(response)

        raise AssertionError("Retry loop ended without a result")

    def _backoff(self, attempt: int) -> None:
        self._sleep(0.25 * (2**attempt))

    def _http_error(self, response: httpx.Response) -> ProviderError:
        provider_code: str | None = None
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("code"), str):
                provider_code = payload["code"]
        except ValueError:
            pass

        status = response.status_code
        if status in {401, 403}:
            return self._error(
                ErrorType.UNAUTHORIZED,
                f"{self.source} rejected the configured credentials or plan access.",
                retryable=False,
                http_status=status,
                provider_code=provider_code,
            )
        if status == 429:
            return self._error(
                ErrorType.RATE_LIMITED,
                f"{self.source} rate limit or quota was reached.",
                retryable=True,
                http_status=status,
                provider_code=provider_code,
            )
        if status in {400, 404, 409, 422}:
            return self._error(
                ErrorType.INVALID_INPUT,
                f"{self.source} rejected the request parameters.",
                retryable=False,
                http_status=status,
                provider_code=provider_code,
            )
        return self._error(
            ErrorType.UPSTREAM_ERROR,
            f"{self.source} returned HTTP {status}.",
            retryable=status >= 500,
            http_status=status,
            provider_code=provider_code,
        )

    def _error(
        self,
        error_type: ErrorType,
        message: str,
        *,
        retryable: bool,
        http_status: int | None = None,
        provider_code: str | None = None,
    ) -> ProviderError:
        return ProviderError(
            error_type=error_type,
            message=message,
            retryable=retryable,
            source=self.source,
            retrieved_at=utc_now(),
            http_status=http_status,
            provider_code=provider_code,
        )
