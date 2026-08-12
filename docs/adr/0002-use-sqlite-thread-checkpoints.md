# ADR-0002: Use SQLite for local thread checkpoints

## Status

Accepted on August 12, 2026

## Context

Phase 5 needs multi-turn follow-ups, thread isolation, and recovery after restarting the CLI. The project serves one local user at low volume. It does not need shared accounts, semantic recall across threads, or hosted infrastructure.

Non-functional constraints:

- Security: checkpoints must not enter Git, and deserialization must use a strict safe-type policy.
- Reliability: closing the process must not erase completed turns.
- Cost: persistence should add no hosted service bill.
- Maintainability: the graph should accept either an in-memory or SQLite checkpointer.
- Scale: one synchronous local CLI process is the current target.

## Decision

Use LangGraph `InMemorySaver` in deterministic memory tests. Use `SqliteSaver` for the production CLI. Store the database at `.data/crypto-agent.sqlite3` by default and allow `CHECKPOINT_DB_PATH` to override it.

Pass a validated `thread_id` in LangGraph runtime configuration for each turn. Restrict IDs to 1 through 64 letters, numbers, dots, underscores, or dashes. Configure `JsonPlusSerializer` with no extra MessagePack module allowlist.

Treat this as short-term conversation memory. Do not add vector search, user profiling, or cross-thread long-term memory in Phase 5.

## Consequences

### Positive

- Follow-up questions receive prior messages from the same thread.
- Separate IDs produce isolated histories.
- A new process resumes an existing local thread.
- The MVP gains persistence without database administration or a monthly service cost.

### Negative

- SQLite does not fit concurrent hosted replicas or multiple writers.
- The local database stores conversation text and tool results in plaintext.
- Users must retain a thread ID to resume a specific conversation.

### Neutral

- A hosted version should replace SQLite with a supported database checkpointer while preserving the graph interface.
- Long-term semantic memory remains a separate product and privacy decision.

## Alternatives Considered

### In-memory checkpoints only

Rejected for the CLI because all history disappears on process exit.

### PostgreSQL now

Deferred because a server, credentials, migrations, and operating cost add no Phase 5 payoff for one local user.

### Vector memory

Rejected because the required behavior is exact thread continuity, not semantic recall across conversations. It also expands privacy, retrieval-quality, and evaluation scope.

## References

- https://docs.langchain.com/oss/python/langgraph/add-memory
- https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver
- https://reference.langchain.com/python/langgraph/checkpoints
