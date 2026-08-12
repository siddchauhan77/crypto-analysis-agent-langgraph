# Crypto Market Analysis Agent

A read-only LangGraph agent for current cryptocurrency market data, relevant news, comparisons, and threaded follow-up questions.

The agent does not predict prices, recommend trades, connect to wallets, or execute transactions.

## Current status

Phase 1 is complete. The secret-safe Python environment, configuration contract, redacted provider samples, baseline tests, and verification commands are in place. API clients, LangGraph routing, tools, memory, and the conversational interface arrive in later phases. See [BUILD_PLAN.md](BUILD_PLAN.md) for implemented-versus-planned boundaries.

## Architecture target

```text
User question
    ↓
LangGraph model node
    ↓ chooses a tool
Coin list | Market data | Crypto news
    ↓
Normalized, timestamped result
    ↓
Grounded answer with uncertainty
```

## Required accounts

1. OpenAI API
   - Create an API key at <https://platform.openai.com/settings/organization/api-keys>.
   - Add a small API credit balance and set a usage limit.
2. FreeCryptoAPI
   - Register at <https://freecryptoapi.com/panel/register.php>.
   - Verify the email address, sign in, and copy the API key from the dashboard.
3. NewsAPI
   - Register at <https://newsapi.org/register> as an individual for this local course project.
   - Verify the email address if requested, sign in, and copy the developer API key.

Do not paste keys into chat, source files, screenshots, tests, or Git.

## Local secret setup

Copy `.env.example` to `.env`, then enter the three keys in `.env` on your computer. The repository ignores `.env`.

```bash
cp .env.example .env
```

Expected private file:

```dotenv
OPENAI_API_KEY=your_openai_key
FREECRYPTO_API_KEY=your_freecrypto_key
NEWS_API_KEY=your_newsapi_key
```

## Development setup

Install `uv`, then run:

```bash
uv python install 3.11
uv sync --extra dev
uv run crypto-agent check-config
```

The configuration command reports whether each service is configured. It never prints a credential.

## Verification

```bash
uv run python -c "import langgraph"
uv run ruff check .
uv run pytest
```

Redacted examples of the two live data-provider response shapes are stored in [docs/provider-samples](docs/provider-samples). They contain no article text, current market values, or credentials.

## Safety boundaries

- Read-only market research
- No price predictions
- No buy, sell, or allocation recommendations
- No wallet, exchange, or transaction access
- Current claims require tool data, source names, and retrieval timestamps
- News-based explanations must be labeled as hypotheses unless a source directly establishes causation

## Build plan

See [BUILD_PLAN.md](BUILD_PLAN.md) for the architecture, 25-hour schedule, tests, evaluation targets, and safety boundaries.
