# Crypto Market Analysis Agent: After-Action Report

Closeout date: August 13, 2026  
Release status: Technical MVP complete. FDE observability upgrade added August 23, 2026.
Risk boundary: Read-only market research. No trading, wallet, exchange, or transaction access.

## Outcome

The project moved from a course brief into a deployed crypto research agent with two interfaces. The terminal provides durable SQLite conversations. The browser provides a public-facing research workflow backed by FastAPI and the same LangGraph agent.

The agent routes among three tools:

- Cryptocurrency symbol discovery
- Current market data for one to five symbols
- Recent crypto headlines and snippets

Current claims include a provider and retrieval time. The system separates sourced market facts from news-based interpretation and refuses personalized trade direction.

## Release evidence

Verified August 13, 2026:

- Ruff lint: passed
- Test collection: 68
- Offline tests: 66 passed
- Opt-in live provider tests: 2 skipped during the offline closeout run
- Fixed live evaluation after regression upgrade: 40 of 40 runs passed
- Initial baseline retained as history: 37 of 40 runs passed
- Median regression-run latency: 4.835 seconds
- Estimated OpenAI model cost for the regression run: $0.022025
- Live homepage: HTTP 200
- Live health endpoint: HTTP 200, read-only mode, access code required
- Live browser workflow: BTC and ETH comparison returned current prices, 24-hour changes, a chart, FreeCryptoAPI attribution, and a retrieval timestamp
- Desktop browser console: no observed errors
- Mobile viewport: 375 pixels wide with no horizontal overflow
- Tracked-file credential-pattern scan: no matching credentials

## Decisions and trade-offs

### Explicit LangGraph state machine

Decision: Use an explicit graph instead of hiding orchestration behind a high-level helper.

Payoff: Tool routing, duplicate-call rejection, call limits, and terminal states remain visible and testable.

Cost: More implementation code and more graph-specific tests.

### Sequential tools with a six-call ceiling

Decision: Disable parallel tool calls and cap each turn at six requested calls.

Payoff: Ordered traces, bounded quota use, and simpler duplicate detection.

Cost: Multi-source requests take longer.

### Two memory strategies

Decision: Use SQLite checkpoints locally and bounded browser-visible history on Vercel.

Payoff: Durable local demonstrations without adding hosted database cost. Server-side keys stay outside the browser.

Cost: Browser conversations do not persist across devices or cleared browser storage.

### Read-only product boundary

Decision: Support research while excluding predictions, allocation advice, wallets, exchanges, and transactions.

Payoff: Lower financial risk and a clearer evaluation surface.

Cost: The product does not serve execution-oriented traders.

## What worked

- Typed provider clients kept API quirks outside the agent graph.
- Mocked HTTP tests made the default suite repeatable and free of provider quota use.
- The fixed evaluation set exposed failures hidden by one-off demos.
- Source names and retrieval times created visible evidence in the interface.
- The same core agent served the CLI and browser instead of creating two separate systems.
- The public interface translated tool calls into a workflow a non-technical reviewer can operate.

## What did not work as planned

- The initial baseline had three response-contract misses. Deterministic graph-boundary evidence and regression tests raised the unchanged suite from 37 of 40 to 40 of 40.
- FreeCryptoAPI's free plan did not provide every planned field. Unsupported market-cap and volume fields were removed instead of inferred.
- A provider request initially encoded the multi-symbol separator incorrectly. FreeCryptoAPI required a literal `+`, not `%2B`.
- Vercel does not provide durable SQLite persistence. The browser uses bounded local history instead.
- The browser initially displayed stale test counts as the suite grew. Closeout now reports 66 passing offline tests.
- The project has current-price comparison bars, not historical TradingView-style time-series charts.

## Known production gaps

- Shared access code instead of user authentication
- Best-effort per-instance throttling instead of a shared rate-limit store
- No hosted checkpointer for durable cross-device threads
- No production tracing, alerting, or abuse-response runbook
- No analyst feedback capture linked to failed traces
- No historical price provider or candlestick data
- No formal user study with working crypto analysts

The August 23 upgrade adds a hidden, separately authenticated admin console for redacted per-request execution metadata. It makes the model-to-tool flow inspectable during an interview. It does not close the production gaps above.

These gaps block claims of production ownership or proven analyst adoption.

## FDE interpretation

The project demonstrates the audit, evaluation, and deployment loop in a portfolio setting:

- Audit: translated the course brief and crypto research workflow into explicit requirements and boundaries
- Evaluation: built a fixed 20-case set, ran 40 live trials, and documented failures
- Deployment: shipped a server-side-key browser demo and verified the live workflow

The weakest part is post-deployment measurement. A production engagement would add user feedback, operational metrics, service-level targets, and a business measure tied to revenue, risk, or cost.

## What I would do next

1. Interview three crypto research analysts and map their current research sequence, exceptions, and evidence standards.
2. Add historical price data only if those interviews confirm a repeated comparison need.
3. Add hosted traces and analyst feedback before tuning prompts.
4. Convert observed failures into new evaluation cases.
5. Measure time to a source-backed comparison against the analyst's current workflow.

## Distribution plan

The technical build is closed. The next payoff comes from distribution:

- Record the 90-second demo in `docs/showcase-plan.md`.
- Use the stories in `docs/interview-story-bank.md`.
- Send the live demo and evaluation report to five FDE or AI Solutions Engineering reviewers.
- Ask one question: “What would stop you from trusting this in a real research workflow?”

Do not add another feature before collecting those responses.
