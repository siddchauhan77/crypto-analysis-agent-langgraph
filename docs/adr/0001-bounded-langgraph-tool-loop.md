# ADR-0001: Use a bounded custom LangGraph tool loop

## Status

Accepted on August 12, 2026

## Context

The MVP needs visible model routing, structured tool execution, a per-user-turn safety limit, and deterministic tests. It does not yet need durable memory, multiple agents, or deployment infrastructure.

Non-functional constraints:

- Security: API keys stay in local settings and never enter graph messages.
- Reliability: provider failures remain structured tool results.
- Cost: no more than six model-requested tool calls per user turn.
- Maintainability: model, tool, and graph construction remain separately testable.
- Scale: one local user and low request volume during the course project.

## Decision

Use one `StateGraph` with a model node, LangGraph `ToolNode`, conditional routing, a duplicate-call rejection node, and a tool-limit node. Count requested tool calls since the latest human message so the limit resets for each new turn. Reject an identical tool name and argument set within the same turn. Compile without a checkpointer in Phase 4. Add persistence in Phase 5.

Use `ChatOpenAI` with the configured model and Responses API mode. Bind the three Phase 3 tools with parallel calls disabled so routing traces remain ordered and quota use stays predictable.

## Consequences

### Positive

- Routing and failures remain visible in graph messages.
- Fake-model tests cover behavior without OpenAI cost.
- The call limit works with later threaded persistence.
- A rejected tool request receives matching `ToolMessage` records before the graph ends.

### Negative

- Sequential tool calls increase latency for multi-source questions.
- The model may spend more than one round selecting tools.
- Phase 4 has no cross-process or cross-turn memory.

### Neutral

- Phase 5 must add a checkpointer without changing the core routing loop.

## Alternatives Considered

### LangChain `create_agent`

Rejected for this phase because the course goal requires an explicit LangGraph loop and observable conditional routing.

### Custom manual tool executor

Rejected because `ToolNode` already handles standardized `ToolMessage` creation and aligns with the documented LangGraph pattern.

### Parallel tool calls

Deferred because ordered calls simplify quota control, traces, and the six-call guard. Parallel execution remains an evaluation-driven option.

## References

- https://docs.langchain.com/oss/python/langchain/tools
- https://docs.langchain.com/oss/python/langgraph/quickstart
- https://developers.openai.com/api/docs/guides/tools
