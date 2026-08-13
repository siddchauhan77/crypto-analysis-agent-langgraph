# Phase 6 Evaluation Report

Status: Baseline completed August 12, 2026

## Result

| Metric | Result |
|---|---:|
| Curated cases | 20 |
| Repetitions | 2 |
| Total live runs | 40 |
| Fully passing runs | 37 |
| Overall pass rate | 92.5% |
| Median end-to-end latency | 5.574 seconds |
| Input tokens | 99,704 |
| Cached input tokens | 11,648 |
| Output tokens | 12,168 |
| Estimated OpenAI model cost | $0.021383 |

The estimate uses the reviewed GPT-4o mini text-token prices of $0.15 per million input tokens, $0.075 per million cached input tokens, and $0.60 per million output tokens. It excludes FreeCryptoAPI and NewsAPI plan costs.

## Deterministic checks

| Check | Passes | Rate |
|---|---:|---:|
| Acceptable first tool | 40/40 | 100% |
| Required tools called | 40/40 | 100% |
| Forbidden tools avoided | 40/40 | 100% |
| Expected symbol arguments | 40/40 | 100% |
| Required provider result succeeded | 40/40 | 100% |
| Final response present | 40/40 | 100% |
| Exact retrieval time present | 40/40 | 100% |
| Provider source present | 38/40 | 95% |
| Explicit causal uncertainty | 39/40 | 97.5% |
| No direct trade instruction | 40/40 | 100% |

## Group results

| Group | Passes | Rate |
|---|---:|---:|
| Direct market data | 10/10 | 100% |
| Symbol resolution | 6/6 | 100% |
| Recent news | 8/8 | 100% |
| Multi-tool synthesis | 5/6 | 83.3% |
| Threaded follow-ups | 4/6 | 66.7% |
| Safety | 4/4 | 100% |

## Remaining failures

1. `thread-news-followup`, both repetitions: the agent preserved the correct first publisher, Cointelegraph, but the short follow-up omitted the provider label `NewsAPI`.
2. `synthesis-btc-context`, repetition two: the answer did not claim news caused the price movement, but it omitted an explicit causal-uncertainty sentence required by the rubric.

Manual review: all three outputs remained factually useful and safe. They failed the written response contract. They remain failures in the published score.

## Defect found and corrected

The model sometimes supplied a 2023 start date to the recent-news tool because model knowledge did not establish the current date. NewsAPI rejected that historical range on the developer plan, leading to repeated attempts and missing news context.

The model-facing news tool now exposes query, language, and result limit only. The client requests the newest available provider results. After this change, required provider success improved to 40 of 40 runs.

## Method

- The fixed dataset lives in `evals/cases.jsonl`.
- Every repetition uses a fresh thread namespace.
- Multi-turn cases retain history only inside their own thread.
- Code checks score tool names, tool arguments, provider status, source labels, timestamp presence, uncertainty language, and prohibited trade directions.
- The suite uses no LLM judge. Manual review is reported separately.
- Full outputs and trajectories live in `evals/baseline-results.json`.

This follows LangChain's three evaluation levels: final response, single-step tool selection, and full trajectory. Deterministic checks remain the baseline because they are repeatable and do not add judge-model cost.

## Limits

- The sample contains 20 curated cases, not production traffic.
- Provider data and latency change over time.
- Text heuristics do not prove factual correctness of every sentence.
- The baseline covers a local single-user CLI, not a concurrent hosted service.
- Cost is an estimate based on published model token prices reviewed on August 12, 2026.

## References

- https://docs.langchain.com/langsmith/evaluation-approaches
- https://docs.langchain.com/langsmith/trajectory-evals
- https://developers.openai.com/api/docs/models/gpt-4o-mini
