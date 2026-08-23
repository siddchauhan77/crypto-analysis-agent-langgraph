# Crypto Agent Interview Story Bank

Target roles:

- Forward Deployed Engineer
- AI Solutions Engineer
- Agent Engineer
- AI Product Engineer
- Technical Product or Solutions roles focused on AI workflows

Use these stories as evidence from a portfolio project. Do not describe the app as an enterprise deployment, a trading system, or a product with proven analyst adoption.

## Story 1: Turning an open brief into a bounded agent

Use for: “Tell me about a zero-to-one project,” “How do you work through ambiguity?”

### STAR

Situation: A course brief asked for a crypto agent using LangGraph, OpenAI, market data, news, and memory. It did not define reliability, financial boundaries, or release evidence.

Task: Turn the brief into a testable product a reviewer could use without exposing credentials or presenting speculative financial advice.

Action: I defined a read-only research user, separated goals from non-goals, designed three narrow tools, added source and retrieval-time requirements, capped tool calls, and wrote a fixed evaluation set before treating the demo as complete.

Result: I shipped a CLI and browser interface. The first live baseline passed 37 of 40 repeated runs. I classified the three misses, added deterministic evidence enforcement and regression tests, then passed 40 of 40 on the unchanged set.

### 60-second version

“I started with a broad course brief for a crypto agent. The missing part was a release standard. I narrowed the user promise to read-only market research, designed three tools for symbol lookup, current market data, and recent news, then added source timestamps, a six-call ceiling, and a fixed 20-case evaluation set. I reused the same LangGraph agent in a durable local CLI and a hosted browser interface. The first 40-run evaluation passed 37 runs. I traced the misses to response-contract fields, moved those invariants to the graph boundary, added regression tests, and passed all 40 runs on the unchanged set. The lesson was to define and enforce the operating boundary before polishing the interface.”

One-line proof: “I turned a broad agent brief into a bounded product with three tools, two interfaces, and a 40-run evaluation baseline.”

## Story 2: Debugging a real provider integration failure

Use for: “Tell me about a technical problem you solved,” “How do you debug unfamiliar APIs?”

### STAR

Situation: Multi-symbol requests passed local assumptions but failed against FreeCryptoAPI.

Task: Find whether the failure came from the model, tool schema, HTTP client, or provider contract.

Action: I isolated the client request, compared single-symbol and multi-symbol behavior, inspected the encoded request, and found the provider required a literal `+` separator while the client sent `%2B`. I corrected the request construction and retained mocked plus opt-in live tests.

Result: The BTC and ETH comparison path passed live routing and now returns both symbols in one provider request with one retrieval timestamp.

### 60-second version

“A multi-symbol market request failed even though the tool arguments looked correct. I traced the failure below the agent layer and compared the final HTTP request with the provider's accepted format. The client encoded the plus separator as `%2B`, but FreeCryptoAPI expected a literal `+`. I corrected request construction and kept both mocked contract tests and a small live gate. The BTC and ETH comparison then returned both records from one retrieval. It reinforced a rule I now use: debug agent failures layer by layer instead of changing the prompt first.”

One-line proof: “I traced an apparent agent failure to URL encoding in the provider client and verified the correction with live data.”

## Story 3: Choosing different memory systems for local and hosted use

Use for: “Describe an architecture trade-off,” “How do you balance speed and production needs?”

### CASE

Context: The terminal needed durable thread resume, while the browser ran on Vercel's serverless filesystem.

Action: I used SQLite checkpoints with named thread IDs for the local CLI. For the browser, I sent at most 12 visible messages with each request while keeping API keys on the server.

Stakes: Treating serverless local storage as durable would create unreliable conversation recovery. Adding a hosted database would add scope and operating cost before the demo required cross-device persistence.

Evidence: Local threads resume after process restart. Fresh thread IDs remain isolated. The deployed browser supports bounded follow-ups without exposing provider credentials.

### 60-second version

“The memory requirement changed across environments. The CLI needed durable restart recovery, so I used SQLite checkpoints and explicit thread IDs. The hosted browser ran on Vercel, where local files are temporary, so I did not pretend the same design would persist. Instead, the browser resends a maximum of 12 visible messages and the server keeps all API keys private. This gave the demo useful follow-ups without adding a hosted database. I documented the trade-off: cross-device memory needs a hosted checkpointer in a later production version.”

One-line proof: “I treated memory as an infrastructure decision and used separate local and serverless persistence strategies.”

## Story 4: Using failed evals as product evidence

Use for: “Tell me about a failure,” “How do you evaluate nondeterministic systems?”

### STAR

Situation: Single demo prompts looked successful, but they did not measure repeated model behavior.

Task: Create a repeatable release baseline across routing, grounding, follow-ups, safety, latency, and cost.

Action: I wrote 20 fixed cases, ran each twice in a fresh thread, scored deterministic properties, and saved the full results. I kept the three failed runs in the report, classified their shared root cause, added focused regression tests, and moved deterministic evidence requirements from model prompt compliance to graph-boundary enforcement.

Result: The first baseline reached 37 of 40. The unchanged evaluation set then reached 40 of 40 after the upgrade. The result measures the fixed suite, not production reliability.

### 60-second version

“The biggest risk was mistaking one clean demo for reliable agent behavior. I built 20 fixed cases across market data, symbol checks, news, synthesis, memory, and safety, then ran each twice in a fresh thread. The first run passed 37 of 40. Two answers omitted a provider label and one omitted a causal caveat. I traced all three to deterministic requirements left to prompt compliance. I enforced those fields at the graph boundary, added regression tests, and reran the unchanged suite at 40 of 40. I present this as measured behavior on a fixed set, not production reliability.”

One-line proof: “I converted three failed live runs into root causes, regression tests, a boundary correction, and a 40-of-40 rerun.”

## Story 5: Shipping a safe public demo

Use for: “How do you move from prototype to deployment?” “How do you explain technical systems to users?”

### CASE

Context: The local agent worked, but friends and interviewers needed a browser experience without access to local credentials.

Action: I exposed the existing graph through FastAPI, kept all credentials server-side, added a shared demo code, input and history bounds, no-store caching, security headers, best-effort throttling, a tutorial flow, evidence labels, and responsive charts.

Stakes: A public link without cost and access controls would expose paid model and provider usage. A separate frontend-only mock would not prove the real agent worked.

Evidence: The live homepage and health endpoint return HTTP 200. A browser run produced a sourced BTC and ETH comparison. Desktop console checks showed no errors, and the 375-pixel viewport had no horizontal overflow.

### 60-second version

“I wanted reviewers to use the real agent without getting my API keys. I kept the LangGraph system behind a FastAPI endpoint, stored credentials in server-side environment variables, and added a shared demo code, bounded inputs and history, security headers, no-store caching, and request limits. I also added a short onboarding flow so a non-technical reviewer knows where to start and how to inspect evidence. At closeout, the live workflow returned a sourced BTC and ETH chart, the desktop console showed no errors, and the mobile page had no horizontal overflow.”

One-line proof: “I moved the same tested agent from a local CLI to a guarded browser demo and verified the live workflow.”

## Story 6: Turning an opaque agent run into inspectable evidence

Use for: “How do you debug agents in front of a customer?” “How do you build trust in AI behavior?”

### CASE

Context: The public demo showed a sourced answer, but a technical reviewer could not inspect the request-to-tool path without reading code or running the CLI debugger.

Action: I added a hidden admin route with a separate role code. It records current-turn request bounds, model tool selection, validated arguments, normalized provider output, duration, sources, and the final response. I added recursive credential redaction, response size bounds, no-store headers, and explicit language excluding hidden chain-of-thought.

Stakes: Exposing raw prompts or credentials would create a security problem. Showing a fake static diagram would not prove the live route executed.

Evidence: Four new API tests cover disabled configuration, rejected credentials, role verification, trace structure, and secret redaction. The full offline suite now passes 66 tests, with two live provider tests kept opt-in.

### 60-second version

“The demo returned good answers, but the execution path stayed opaque to a reviewer. I added a separate admin role that runs the same LangGraph workflow and returns redacted current-turn events: request bounds, tool selection, validated arguments, normalized provider output, timing, sources, and the final answer. I did not expose chain-of-thought or system prompts. I tested the authorization boundary and planted a fake API key in a tool response to prove the trace redactor removes it. The upgrade changed the demo from ‘trust the answer’ to ‘inspect the bounded execution.’”

One-line proof: “I added role-separated, secret-redacted execution evidence to the same live agent path.”

## Tell me about yourself bridge

“I work at the point where a user workflow becomes a tested AI system. In this project, I took a broad crypto-agent brief, narrowed it to read-only research, integrated two live data providers through three tools, and built an explicit LangGraph loop with memory, cost limits, and failure handling. I created a 20-case evaluation set, ran 40 live trials, and deployed the same agent through a browser interface. The first run passed 37 of 40. I classified the misses, enforced the deterministic contract at the graph boundary, added regressions, and passed 40 of 40 on the unchanged set. That combination of workflow translation, implementation, evaluation, and user-facing delivery is why I am targeting FDE and AI Solutions Engineering roles.”

## Credibility boundaries

Skills proved:

- Python API integration
- LangGraph orchestration
- Tool schema and provider error design
- Local durable memory
- Serverless delivery trade-offs
- Agent evaluation
- Safety and cost boundaries
- Browser product delivery

Skills not yet proved by this project:

- Enterprise stakeholder management
- Production adoption by working analysts
- Shared multi-user persistence
- Full observability and incident response
- Revenue impact, analyst time savings, or risk reduction
- High-volume or multi-region scale

## Practice questions

1. Why did this need an agent instead of a fixed workflow?
2. What were the three failed evaluation runs, how did you address them, and why does 40 of 40 still not mean production reliability?
3. Why did you choose SQLite locally but not on Vercel?
4. What would you measure with three real crypto analysts?
5. Where would you add human approval if the product gained external actions?
6. What would fail first at 1,000 users?
7. How did you keep model cost bounded?
8. Which parts are deterministic and which depend on model behavior?

## Interviewer questions

- “Which customer workflow would this team most want an FDE to audit in the first 30 days?”
- “How does your team convert production failures into evaluation cases?”
- “Which outcome matters most for your AI deployments: revenue, risk, or operating cost?”
- “Where does your team draw the boundary between model autonomy and human approval?”

Rate these stories 1–5. Note which story feels least natural when spoken aloud, then rewrite only that story in your own words.
