# Provider Client Contracts

Status: Implemented in Phase 2 on August 12, 2026

## Boundary

These clients consume external APIs. They do not expose a public HTTP API. The internal Pydantic models form the stable boundary used by later LangChain tools.

## Authentication

• FreeCryptoAPI sends `Authorization: Bearer <key>`.

• NewsAPI sends `X-Api-Key: <key>`.

• Keys never enter URLs, result models, errors, fixtures, or logs.

## Success contracts

### Cryptocurrency list

Returns a bounded list of symbols, names, provider source, total supported count, source name, and UTC retrieval time.

### Market data

Returns up to five symbols with price, 24-hour change, high, low, BTC-denominated price, source exchange, provider timestamp, source name, and UTC retrieval time.

The response lists requested symbols missing from a partial provider response. Missing numeric fields remain `null`. They never become zero.

The configured free plan does not expose market capitalization or volume through `/getData`. `/getTop` requires a plan upgrade. Those fields are outside the MVP contract.

### News search

Returns up to ten articles with title, publisher, publication time, URL, description, author, total results, source name, and UTC retrieval time.

NewsAPI supplies headlines and truncated snippets rather than full article text. The Developer plan also has a 24-hour publication delay.

## Error catalog

| Error type | Meaning | Retryable |
|---|---|---|
| `invalid_input` | Local validation or provider parameter rejection | No |
| `unauthorized` | Invalid credentials or unavailable plan access | No |
| `rate_limited` | Provider quota or rate limit reached | Yes, after waiting |
| `timeout` | Request exceeded the bounded timeout and retry count | Yes |
| `upstream_error` | Network, malformed response, or provider failure | Depends on cause |
| `empty_result` | Valid bounded query returned no records | No |

Every error includes a safe message, provider source, retry flag, and UTC retrieval time. Provider response bodies and credentials are not copied into error messages.

## Retry policy

• Retry timeouts, network failures, and HTTP 5xx responses.

• Use exponential waits starting at 0.25 seconds.

• Stop after the configured bounded retry count.

• Do not retry invalid input or authentication failures.

• Return rate-limit errors to the caller instead of immediately consuming more quota.

## Evolution rule

Provider-specific response models remain inside each client module. Later tools depend only on the normalized contracts in `models.py`. A provider field addition does not alter the internal contract unless the project adds and tests it deliberately.
