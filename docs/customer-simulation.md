# Composite Analyst Scenario

## Evidence boundary

This is a fictional composite workflow. No customer, employer, analyst, or research team used Signal Desk. The scenario is a design and demo artifact based on public descriptions of crypto-research work. It does not prove demand, adoption, satisfaction, accuracy in production, or investment value.

## Why this workflow

Public crypto-research material points to a recurring job: turn volatile market information into concise, decision-ready research without presenting a trading recommendation.

• Allium's public Blockchain Research Analyst role describes converting blockchain data into actionable insights, research dashboards, reports, concise market updates, and data-driven narratives for institutional and strategy audiences. [Allium role](https://jobs.ashbyhq.com/allium/46da49f4-3b4e-43fd-97b1-039407f7d621/)

• Elliptic's public Senior Data Analyst role describes investigating digital-asset patterns, building reproducible analyses, and producing clear narratives and visuals for Product, Marketing, Sales, and Policy. [Elliptic role](https://jobs.ashbyhq.com/elliptic/89ad8b39-6858-45a3-8423-545bf2ebdcfa/)

• Binance Research publishes monthly market insights that summarize developments, charts, and upcoming events. Its own disclaimer says research is informational and not an investment recommendation. [Binance Research](https://www.binance.com/en/research)

## The composite user

**Role:** Research analyst at a small digital-asset intelligence team.

**Job to be done:** Before a daily research stand-up, produce a 10-minute briefing that gives the research lead current facts, relevant coverage, source links, and the limits of any interpretation.

**Prompt in Signal Desk:**

> I am preparing a 10-minute research brief. Compare BTC and ETH using current price and 24-hour change, then summarize three recent headlines. Separate measured facts from possible explanations. Do not make a trading recommendation.

## Expected output

| Needed in the brief | Signal Desk behavior |
| --- | --- |
| Current price comparison | Retrieves BTC and ETH from the market-data provider and renders a USD chart when data is available. |
| Relevant coverage | Searches recent crypto headlines and returns source links. |
| Evidence timing | Names providers and reports retrieval times for tool-backed facts. |
| Interpretation discipline | Labels news-based explanations as hypotheses unless a source establishes causation. |
| Decision boundary | Does not issue a buy, sell, allocation, or price-prediction recommendation. |

## Acceptance criteria

• One request handles a price comparison plus news context.

• The response distinguishes observations from explanations.

• The reader can inspect provider names, retrieval times, and cited headline links.

• Missing data and provider failures stay visible. They do not become zero values or invented context.

• The analyst retains responsibility for the research conclusion, any report sent to others, and every financial decision.

## Known gaps

This is a bounded portfolio demonstration. It does not include on-chain metrics, proprietary research, authentication, shared durable memory, organization-level rate limits, production audit retention, or user research. The chart is a current-price comparison, not historical technical analysis.

## How to demo it

1. Open the [live interface](https://crypto-analysis-agent-langgraph.vercel.app/).
2. Select **Run analyst brief** under **Try an example**.
3. Inspect the chart, citations, provider names, and retrieval times.
4. Ask a follow-up such as: “Which asset moved more in the reported 24-hour period?”
5. Ask for a trade recommendation to show the safety boundary.
