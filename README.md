# Greenlight

Explicit approval for xStocks trades inside Hermes Agent.

Greenlight turns a trade request into a simulated proposal with risk score and remaining daily cap, surfaces it in a native Desktop pane, and only releases an unsigned transaction after the user gives the green light. It never holds keys.

## What it does
- Accepts natural-language trade intents
- Builds unsigned transactions via @xstocker/agent-sdk
- Runs mandatory simulation + risk scoring
- Enforces local daily USD caps
- Shows a native Hermes Desktop approval pane
- Stores verifiable local receipts
- Hands the user a solanaPayUrl or unsigned transaction only after approval

## Quick start
```bash
hermes plugins install https://github.com/Datwebguy/greenlight
```

Then ask Hermes:
```
Propose buying $25 of NVDAx
```
Approve in the Desktop pane.

## Surfaces used
- **Tools:** `propose_trade`, `get_trade_status`, `list_receipts`
- **Hooks:** approval gating
- **Desktop Plugin SDK:** approval pane
- **Bundled skill:** `greenlight`

## Important
- Non-custodial. The plugin never signs or broadcasts.
- All real movement requires explicit approval.
- Do not list Claude (or any Anthropic model) as author or co-author of this plugin or its commits.

## Links
- Agent SDK: https://www.npmjs.com/package/@xstocker/agent-sdk
- xStocks docs: https://docs.xstocks.fi
- Hermes plugin guide: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md
- Desktop SDK: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md
- Catalog submission: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md

## Configuration
Set under `plugins.entries.greenlight.settings` (or in the Desktop Plugins settings page):

| Key | Default | Meaning |
|---|---|---|
| `daily_cap_usd` | 250 | Max USD value of approved plus pending proposals per UTC day |
| `proposal_ttl_minutes` | 10 | Pending proposals expire after this long |
| `max_quote_drift_pct` | 1.0 | Release is refused if the quote at approval is worse than the approved one by more than this |

SOL-denominated legs have no USD quote, so they require `max_usd`, which is then used as the trade value for cap accounting.

## How the flow stays safe
1. `propose_trade` simulates the order against the live xStocks API and stores only the quote. No transaction is stored or returned.
2. The Desktop pane shows quote, risk score and cap. Approve or Reject updates local state.
3. On approval the order is rebuilt fresh (unsigned transactions expire in about a minute) and released only if the quote has not drifted.
4. Every decision writes a hash-chained local receipt; `list_receipts` reports whether the chain verifies.
5. A `pre_tool_call` hook blocks any other tool from carrying an xStocks order link that was not released by an approved proposal.

## Disclosure
- Network: calls `api.xstocker.com` and `xstocker.com` through `@xstocker/agent-sdk`. No other third-party services, no telemetry.
- On first use it runs `npm install @xstocker/agent-sdk@1.4.0 --ignore-scripts` into `<HERMES_HOME>/plugin-data/greenlight/node` (needs Node.js 18+ and npm).
- Spawns a short-lived `node` process per SDK call.
- Writes only to `<HERMES_HOME>/plugin-data/greenlight/` (state and receipts). Reads no credentials and holds no keys.

## Development
```bash
pip install pytest fastapi httpx
python -m pytest tests
```
