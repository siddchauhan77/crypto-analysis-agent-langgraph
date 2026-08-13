# Public Showcase Plan

## What someone can use today

The project now has a hosted browser demo and a local terminal chat. Both retrieve current crypto market data and recent news, choose tools through LangGraph, and refuse trade directions. The browser resends bounded visible history. The terminal also supports durable named threads and restart recovery.

Start it:

```bash
uv sync --extra dev
uv run crypto-agent chat
```

Start the browser locally:

```bash
vercel dev
```

Suggested live sequence:

1. Ask: `Compare BTC and ETH using current price and 24-hour percentage change.`
2. Ask: `Which of those two moved more?`
3. Enter: `history`
4. Copy the displayed thread ID and enter: `quit`
5. Restart with: `uv run crypto-agent chat --thread THREAD_ID`
6. Ask: `Should I buy the larger mover today?`

This sequence shows live tools, grounded data, memory, restart recovery, and the safety boundary.

## Sharing options

### Option 1: Screen-share the CLI

Best for a friend or interview call. You operate the keys and control API spend. The viewer sees real behavior without receiving repository or credential access.

### Option 2: Send a 90-second recording

Best default for LinkedIn, a portfolio page, and direct outreach. Show the user question, tool-status lines, answer source and timestamp, follow-up memory, and safety refusal. End on the measured regression story: 37 of 40, three classified failures, then 40 of 40 on the unchanged set.

### Option 3: Public repository

Best for technical reviewers. Publish only after Phase 8 confirms no credentials, private checkpoints, or unsuitable generated output. Lead reviewers to the README, architecture diagram, evaluation report, and fixed cases.

### Option 4: Hosted interactive demo

Use the access-code-protected Vercel deployment for a live portfolio walkthrough. The app keeps keys server-side and applies bounded inputs, visible-history limits, a six-call graph limit, and best-effort throttling. Keep provider spending limits active because serverless instances do not share the local request counter.

## 90-second video structure

| Time | Show | Explain |
|---|---|---|
| 0-10 sec | One-sentence problem and architecture | The agent chooses between market, symbol, and news tools. |
| 10-35 sec | Browser BTC and ETH comparison | Current claims come from an API result with visible source and timestamp chips. |
| 35-50 sec | “Which of those two…” follow-up | Bounded visible history preserves the browser conversation. |
| 50-65 sec | Architecture diagram | Explain browser history versus durable local SQLite threads. |
| 65-75 sec | Buy-or-sell request | The system gives analysis but no trade direction. |
| 75-90 sec | Evaluation report | 20 fixed cases, two runs each, initial 37/40, regression 40/40, $0.022025 estimated model cost. |

## Public positioning

Use this line:

> I built a read-only crypto research agent that selects live market and news tools, preserves isolated conversation threads, and ships with a repeated 20-case evaluation set. Its first run scored 37 of 40. I classified the three misses, added deterministic response-contract enforcement and regression tests, then passed 40 of 40 on the unchanged set at an estimated OpenAI cost of $0.022025.

Do not call it a trading bot, financial adviser, prediction engine, or production financial product.

## Release gate

- Phase 7: browser interface, FastAPI boundary, responsive checks, and hosted demo implemented. Recording remains.
- Phase 8: run clean-install QA, secret scanning, public-link checks, and the final repository visibility decision.
