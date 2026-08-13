# Public Showcase Plan

## What someone can use today

The working product is a local terminal chat. It retrieves current crypto market data and recent news, chooses tools through LangGraph, remembers named threads, and refuses trade directions.

Start it:

```bash
uv sync --extra dev
uv run crypto-agent chat
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

Best default for LinkedIn, a portfolio page, and direct outreach. Show the user question, tool-status lines, answer source and timestamp, follow-up memory, and safety refusal. End on the 92.5% evaluation result.

### Option 3: Public repository

Best for technical reviewers. Publish only after Phase 8 confirms no credentials, private checkpoints, or unsuitable generated output. Lead reviewers to the README, architecture diagram, evaluation report, and fixed cases.

### Option 4: Hosted interactive demo

Defer until the local MVP release passes Phase 8. A hosted version needs server-side keys, per-IP or per-session limits, daily spend caps, abuse controls, isolated thread storage, error monitoring, and a clear analysis-only disclaimer. A public form without those controls exposes API spend.

## 90-second video structure

| Time | Show | Explain |
|---|---|---|
| 0-10 sec | One-sentence problem and architecture | The agent chooses between market, symbol, and news tools. |
| 10-35 sec | BTC and ETH comparison | Current claims come from an API result with source and timestamp. |
| 35-50 sec | “Which of those two…” follow-up | SQLite checkpoints preserve thread context. |
| 50-65 sec | Close and resume the thread | Memory survives a process restart. |
| 65-75 sec | Buy-or-sell request | The system gives analysis but no trade direction. |
| 75-90 sec | Evaluation report | 20 fixed cases, two runs each, 92.5% pass rate, $0.021383 estimated model cost. |

## Public positioning

Use this line:

> I built a read-only crypto research agent that selects live market and news tools, preserves isolated conversation threads, and ships with a repeated 20-case evaluation baseline. It scored 92.5% across 40 live runs at an estimated OpenAI cost of $0.021383.

Do not call it a trading bot, financial adviser, prediction engine, or production financial product.

## Release gate

- Phase 7: record the demo, add sample conversations, and finish portfolio copy.
- Phase 8: run clean-install QA, secret scanning, public-link checks, and the final repository visibility decision.
