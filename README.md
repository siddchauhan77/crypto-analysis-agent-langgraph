# Crypto Market Analysis Agent

A read-only LangGraph agent for current cryptocurrency market data, relevant news, comparisons, and threaded follow-up questions.

The agent does not predict prices, recommend trades, connect to wallets, or execute transactions.

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

## Build plan

See [BUILD_PLAN.md](BUILD_PLAN.md) for the architecture, 25-hour schedule, tests, evaluation targets, and safety boundaries.

