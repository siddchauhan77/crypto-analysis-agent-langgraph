# FDE Readiness Audit

Audit date: August 23, 2026  
Target reviewer: Forward Deployed Engineer hiring manager  
Verdict: Ready as a strong portfolio MVP. Not evidence of production ownership or customer adoption.

## Hiring-manager scorecard

| Signal | Score | Evidence | Remaining gap |
|---|---:|---|---|
| Problem framing | 8/10 | Read-only crypto research boundary, explicit non-goals | No verified analyst discovery |
| Implementation | 9/10 | Typed clients, three tools, explicit bounded LangGraph loop, two interfaces | No multi-user hosted state |
| Evaluation | 9/10 | Fixed 20-case set, repeated 40-run baseline, failed cases retained | Fixed-set performance is not field reliability |
| Observability | 8/10 | Admin trace shows redacted request, tool, provider, timing, and response events | No retained or centralized production traces |
| Security and cost | 7/10 | Server-side keys, separate demo and admin codes, redaction, limits | Shared secrets and per-instance rate limiting |
| User evidence | 3/10 | Clear target user and demo workflow | No research-analyst trials or outcome measure |
| Communication | 9/10 | Architecture, ADRs, evaluation report, known limits, interview stories | Needs a short recorded walkthrough |

Overall: 7.6/10 as FDE portfolio proof. The weakest signal is customer deployment evidence, not code volume.

## Agent-experience maturity

Highest fully satisfied level: Level 1, Tool.

The product is functional and bounded. It has partial Level 2 behavior through visible history, follow-up context, source cues, and an adaptive chart. It does not retain user preferences or adapt across durable hosted sessions.

Pattern score: 8/12.

| Pattern | Score | Reason |
|---|---:|---|
| Intent handshake | 1/2 | Tutorial and examples exist. Clarification is model-dependent. |
| Confidence cues | 2/2 | Sources, timestamps, uncertainty rules, and visible boundaries. |
| Adaptive canvas | 1/2 | Market results receive a chart. Other results remain conversational. |
| Escape hatch | 1/2 | New session exists. In-flight cancellation does not. |
| Memory in motion | 1/2 | Bounded browser history and durable local threads. No hosted durable memory. |
| Generative momentum | 2/2 | Example prompts reach useful first output quickly. |

Trust stage: Stage 1, Functional.

## One-level upgrade shipped

The highest-leverage upgrade was not another data source. It was execution visibility.

The hidden admin console now answers five reviewer questions:

1. What entered the system?
2. Which tool did the model select?
3. Which validated arguments went to the tool?
4. What normalized evidence came back?
5. What grounded answer did the user receive?

It also gives a knowledgeable reviewer an interpretation frame:

- Probabilistic model decision
- Deterministic execution controls
- External evidence and provenance
- Explicit limits on what the trace establishes

Controls:

- Separate `ADMIN_ACCESS_CODE`
- Hidden activation through `?admin=1`
- Request-local trace only
- Recursive credential-field redaction
- Bounded list and string serialization
- No-store response headers
- No chain-of-thought or system-prompt exposure

## Showcase boundary

Say:

“This is a deployed, evaluated portfolio MVP for read-only crypto research. It demonstrates workflow translation, agent orchestration, failure analysis, and role-separated execution inspection.”

Do not say:

“This is production-ready,” “analysts use this,” or “40 of 40 proves reliability.”

## Evidence needed for the next score increase

Run five task-based sessions with three working crypto researchers. Measure time to a source-backed comparison, corrections per answer, trace usefulness, and willingness to reuse the tool. Convert every observed failure into an evaluation case.

That evidence matters more than adding a fourth provider or another visual panel.
