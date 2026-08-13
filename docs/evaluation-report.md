# Phase 6 Evaluation and Regression Report

Status: Initial baseline completed August 12, 2026. Regression run completed August 13, 2026.

## Result

| Metric | Result |
|---|---:|
| Curated cases | 20 |
| Repetitions | 2 |
| Total live runs | 40 |
| Fully passing runs | 40 |
| Overall pass rate | 100% on the fixed set |
| Median end-to-end latency | 4.835 seconds |
| Input tokens | 113,063 |
| Cached input tokens | 16,512 |
| Output tokens | 10,507 |
| Estimated OpenAI model cost | $0.022025 |

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
| Provider source present | 40/40 | 100% |
| Explicit causal uncertainty | 40/40 | 100% |
| No direct trade instruction | 40/40 | 100% |

## Group results

| Group | Passes | Rate |
|---|---:|---:|
| Direct market data | 10/10 | 100% |
| Symbol resolution | 6/6 | 100% |
| Recent news | 8/8 | 100% |
| Multi-tool synthesis | 6/6 | 100% |
| Threaded follow-ups | 6/6 | 100% |
| Safety | 4/4 | 100% |

## Regression outcome

The initial baseline passed 37 of 40 runs. The three failures were factually useful and safe, but they missed deterministic response-contract fields. The original evaluation cases remain unchanged.

| Initial failure | Root cause | Change | Permanent regression coverage | New result |
|---|---|---|---|---|
| `thread-news-followup`, repetition one | The model named Cointelegraph but omitted `NewsAPI`. Provider attribution depended on prompt compliance. | Read the current turn's structured tool evidence and append a missing provider label and exact retrieval time. | Graph-routing test asserts provider and timestamp evidence after tool execution. | Passed |
| `thread-news-followup`, repetition two | Same response-contract weakness under model variation. | Same deterministic graph-boundary enforcement. | Original live case remains in the fixed set and the graph test covers the invariant. | Passed |
| `synthesis-btc-context`, repetition two | The answer avoided a causal claim but omitted the rubric's explicit uncertainty sentence. | When market and news tools both run, append a causal caveat if the answer lacks one. | Graph-routing test combines both tools and asserts the exact caveat. | Passed |

The regression run passed 40 of 40. This closes the three recorded defects for this fixed suite. It does not prove performance on untested prompts or production traffic.

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
