# Current Architecture

Status: Phase 7 implemented August 12, 2026. Admin trace upgrade added August 23, 2026.

## Interface status

The project has an implemented local terminal application and an implemented browser interface backed by FastAPI. The terminal uses durable local SQLite checkpoints. The hosted browser resends bounded visible history because Vercel's serverless filesystem does not support persistent SQLite.

Run the current interface with:

```bash
uv run crypto-agent chat
```

Run the browser-compatible local environment with:

```bash
vercel dev
```

## Requirements

Functional:

- Route current market questions to FreeCryptoAPI market data.
- Route recent-news questions to NewsAPI.
- Route unknown-symbol questions to symbol discovery.
- Return tool results to the model for a grounded answer.
- End without a tool for greetings and timeless explanations.

Non-functional:

- Keep API keys outside graph messages and traces.
- Limit each user turn to six requested tool calls.
- Reject identical repeated calls before another provider request.
- Keep provider and model retries bounded.
- Make nodes, routes, tool arguments, and failures observable.
- Keep default tests free of OpenAI cost and provider quota use.
- Preserve follow-up context inside a named thread.
- Isolate messages between thread IDs.
- Resume local threads after a process restart.

## Implemented local runtime

```mermaid
flowchart TD
    U["User"] --> CLI["Terminal chat interface<br>crypto-agent chat"]
    CLI --> S["SQLite checkpointer<br>local conversation memory"]
    S --> M["Model node<br>System prompt plus thread messages"]
    M --> R{"Tool calls?"}
    R -->|"No"| E["End with grounded answer"]
    R -->|"More than six"| L["Tool-limit node"]
    R -->|"Identical repeat"| D["Duplicate-call rejection"]
    R -->|"Valid request"| T["LangGraph ToolNode"]
    T --> C["Typed Phase 2 clients"]
    C --> F["FreeCryptoAPI"]
    C --> N["NewsAPI"]
    F --> T
    N --> T
    T --> M
    D --> M
    L --> E
    E --> S
```

## Implemented browser delivery layer

The public-demo architecture keeps API keys on the server and reuses the existing graph, tools, evaluation cases, and safety rules. The browser stores at most 12 visible messages locally and resends them with the next turn.

```mermaid
flowchart LR
    B["Browser chat UI<br>bounded local history"] -->|"HTTPS request plus visible history"| A["FastAPI service"]
    A --> G["Existing LangGraph agent"]
    G --> O["OpenAI model"]
    G --> FC["FreeCryptoAPI"]
    G --> NA["NewsAPI"]
    A -->|"Grounded response plus sources"| B

    K["Server-side environment variables"] -.-> A
    RL["Rate and spending limits"] -.-> A
```

Current public controls:

- Browser loading, error, source, timestamp, and safety states.
- A server-side FastAPI endpoint that owns all three credentials.
- A shared demo access code stored in browser session storage.
- Bounded inputs, bounded history, security headers, no-store caching, and best-effort throttling.
- Responsive browser verification at desktop and 375-pixel mobile width.

## Admin observability path

The hidden `?admin=1` route adds an authenticated inspector for one current turn. It accepts a separate `ADMIN_ACCESS_CODE` when configured. The portfolio deployment also has a high-entropy bootstrap credential whose SHA-256 verifier is stored in source while the raw value stays outside Git. The environment value takes precedence for rotation. The normal demo code does not grant admin access.

```mermaid
flowchart LR
    U["Admin question"] --> RB["Role boundary<br>separate admin code"]
    RB --> A["FastAPI admin endpoint"]
    A --> G["Existing LangGraph agent"]
    G --> M["Model tool selection"]
    M --> T["Typed read-only tool"]
    T --> P["External provider"]
    P --> T
    T --> G
    G --> R["Grounded answer"]
    G --> X["Trace builder"]
    X --> D["Recursive secret redaction<br>and size bounds"]
    D --> UI["Admin execution console"]
    R --> UI
```

The console exposes request bounds, selected tool names and arguments, normalized tool output, sources, retrieval times, duration, and the final answer. Its interpretation layer separates three planes:

- Model plane: probabilistic intent interpretation and tool selection.
- Control plane: deterministic schemas, tool budget, duplicate rejection, redaction, and response contract.
- Evidence plane: external provider payload, source, and retrieval time.

The operator readout labels routing, evidence counts, budget use, and trace scope as observed or bounded facts. It does not infer provider truth, causality, or production reliability. The console excludes model chain-of-thought and system prompts. Trace responses use the same no-store policy as public responses and are not retained server-side.

Admin limitations:

- A shared secret is role separation for a portfolio demo, not identity-based authorization.
- Traces are request-local and disappear after the browser session.
- The in-memory request limiter is per serverless instance.
- Production use needs centralized tracing, identity, retention rules, and incident review.

Remaining production upgrades:

- Replace the shared code with user authentication for broader access.
- Add a shared rate-limit store and account-level daily spending controls.
- Add a hosted checkpointer if durable cross-device threads become a requirement.
- Add deployment tracing, alerting, and abuse-response procedures.

## Key trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| Explicit `StateGraph` | Visible course-faithful routing | More code than `create_agent` |
| Sequential tools | Ordered traces and predictable quota | Higher multi-source latency |
| Six-call limit | Bounded cost and loops | Complex questions may need narrowing |
| Fake-model default tests | Stable and free routing tests | Live model behavior still needs a small gate |
| SQLite checkpointer | Durable local resume with no service cost | Local-only storage and no multi-process scaling |
| Explicit thread IDs | Clear isolation and portable CLI resume | User must retain the ID |
| Strict serializer policy | Limits checkpoint deserialization to safe built-in types | Custom serialized classes need explicit review |

## Failure handling

- Provider authentication, timeout, quota, empty result, and upstream failures remain structured tool content.
- Invalid tool arguments return through LangGraph's tool error handling.
- A seventh requested call receives matching tool errors and a final limit message.
- A duplicate request receives a synthetic tool error, then returns to the model for explanation.
- Missing provider values remain missing instead of becoming zero.
- Provider errors display without closing the CLI. The active checkpoint stays available for retry.

## Thread lifecycle

1. `chat` generates a safe thread ID, or validates the ID passed with `--thread`.
2. LangGraph receives the ID in `configurable.thread_id` on every turn.
3. `SqliteSaver` loads the latest checkpoint before the model runs and writes the new state after graph steps.
4. `new` switches to an empty generated ID. `resume` switches to a validated named ID.
5. `history` shows human messages and final agent answers. It hides raw tool payloads.
6. Closing and reopening the CLI reconnects to the same local database.

## Security and cost

- `ChatOpenAI` receives the API key from validated local settings.
- Provider credentials remain inside their HTTP clients.
- The graph stores tool names, arguments, outputs, and messages, never credentials.
- The checkpoint database contains conversation content and tool results. `.data/` is Git-ignored.
- Users should not paste secrets into prompts. Local file access remains the host operating system's responsibility.
- Default tests use fake model messages and mocked HTTP transports.
- Live provider and model checks require intentional commands.

See [ADR-0001](adr/0001-bounded-langgraph-tool-loop.md) for loop decisions and [ADR-0002](adr/0002-use-sqlite-thread-checkpoints.md) for persistence decisions.
