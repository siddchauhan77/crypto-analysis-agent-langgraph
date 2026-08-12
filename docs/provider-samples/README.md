# Provider response samples

These files document response shapes observed from authenticated live requests on August 12, 2026.

They preserve provider field names and JSON value types. Market values, article content, publisher details, URLs, timestamps, totals, and exchange identifiers are redacted. API keys never appear in request URLs, samples, logs, or Git history.

These samples are documentation, not deterministic test fixtures. Phase 2 will add synthetic fixtures for client contract tests.

## Phase 2 schema decision

The observed FreeCryptoAPI `/getData` response contains price, daily change, daily high and low, BTC conversion, source exchange, and provider date fields. It does not contain coin name, market capitalization, or volume. Phase 2 must inspect `/getTop` before finalizing the normalized market-data model. Missing values must remain missing rather than being represented as zero.
