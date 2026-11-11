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

## Judges, start here
No wallet and no funds needed: install, enable, then run `/greenlight demo` (or click **Run demo** in the pane). It pulls a **live** xStocks quote, scores the risk, shows the approval pane, and lets you approve or reject. Approving a demo writes a real receipt but never releases a transaction.

| Step | What happens |
|---|---|
| 1. Propose | `propose_trade` simulates the order against the live xStocks API; only the quote is kept |
| 2. Review | Pane shows quote, price, fee, slippage, risk factors and (if set) your daily cap |
| 3. Approve | The order is rebuilt fresh and checked for quote drift, then released as an unsigned `solanaPayUrl` |
| 4. Sign | Your wallet signs and sends. Greenlight never touches keys |
| 5. Receipt | A hash-chained local receipt is written; `list_receipts` verifies the chain |

## Quick start
```bash
hermes plugins install https://github.com/Datwebguy/greenlight
hermes plugins enable greenlight
```
Then turn on **Greenlight** in the Desktop app under Capabilities > Plugins, and set your public wallet address as `default_wallet` in the plugin's settings page.

Then ask Hermes:
```
Propose buying $25 of NVDAx
```
Approve in the Desktop pane. Prefer the terminal or a chat app? Type `/greenlight approve` (or `/greenlight reject`) instead.

## Why Greenlight
- **Approval is a hard gate, not a prompt.** The transaction does not exist in local state until you approve, and is rebuilt fresh at that moment.
- **You see what matters first:** quote, price, fee, slippage, a risk score with its factors, and how much of your daily cap is left (if you set one).
- **No built-in limits, only the ones you set.** Any amount, any xStock the API lists, any pay token the API accepts. Approval is the one thing that is always required.
- **Guardrails you set:** daily cap, per-trade limit, allowed tickers, quote-drift limit.
- **Works where you work:** Desktop pane and status-bar chip, plus `/greenlight` in the CLI and messaging gateways.
- **Auditable:** hash-chained local receipts; any edit is detected.

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

## How it works
```mermaid
sequenceDiagram
    participant U as User
    participant H as Hermes agent
    participant G as Greenlight
    participant X as xStocks API
    U->>H: "Buy $25 of NVDAx"
    H->>G: propose_trade
    G->>X: build order (simulation)
    X-->>G: quote + unsigned tx
    Note over G: keeps only the quote, discards the tx
    G-->>H: proposal + risk, NO transaction
    G-->>U: Desktop pane / chip / notification
    U->>G: Approve (pane or /greenlight approve)
    G->>X: rebuild order fresh
    G-->>G: refuse if quote drifted
    G-->>H: get_trade_status releases solanaPayUrl
    H-->>U: link; wallet signs and sends
    G-->>G: write hash-chained receipt
```

## What's real and what's simulated
- **Real:** quotes, fees, slippage and the unsigned order come from the live xStocks API through the official SDK. Approval state, caps and receipts are real local state.
- **Simulated:** "simulation" here means building the order against the live API to get a real route and quote before anything is shown. It is not an on-chain dry run, and a quote can move before you sign.
- **Not done by Greenlight:** signing, broadcasting and balance checks. Your wallet does those.
- **Demo mode:** the flow is real but uses a placeholder wallet, ignores your limits and never releases a transaction.

## Limits you should know about
- Approval gating protects against the *agent* acting without you. It does not protect against a compromised machine: anything running as your user can edit local state.
- The `pre_tool_call` gate only recognises xStocks Solana Pay links; it is a safety net, not a sandbox.
- The risk score is a transparent heuristic (size vs your cap, slippage, fee, pay token), not financial advice or a prediction.
- Local state is a JSON file with advisory locking; it targets one user on one machine.

## Configuration
Set under `plugins.entries.greenlight.settings` (or in the Desktop Plugins settings page):

| Key | Default | Meaning |
|---|---|---|
| `daily_cap_usd` | 0 (off) | Optional max USD value of approved plus pending proposals per UTC day |
| `proposal_ttl_minutes` | 10 | Pending proposals expire after this long |
| `max_trade_usd` | 0 (off) | Optional: reject any single trade above this value |
| `default_wallet` | empty | Your public Solana address, used when a request names none |
| `allowed_assets` | empty | Comma-separated tickers the plugin may propose (empty allows all) |
| `max_quote_drift_pct` | 1.0 | Release is refused if the quote at approval is worse than the approved one by more than this |

All limits are off until you set them. SOL-denominated legs have no USD quote, so when you have set a cap or per-trade limit they need `max_usd` to be checked against it; with no limits set they go through unpriced.

## How the flow stays safe
1. `propose_trade` simulates the order against the live xStocks API and stores only the quote. No transaction is stored or returned.
2. The Desktop pane shows quote, risk score and cap. Approve or Reject updates local state.
3. On approval the order is rebuilt fresh (unsigned transactions expire in about a minute) and released only if the quote has not drifted.
4. Every decision writes a hash-chained local receipt; `list_receipts` reports whether the chain verifies.
5. A `pre_llm_call` reminder keeps the model honest about open proposals, and a `pre_tool_call` hook blocks any other tool from carrying an xStocks order link that was not released by an approved proposal.

## Slash command
`/greenlight` shows pending trades and your cap. `/greenlight approve [id]`, `/greenlight reject [id]` and `/greenlight receipts` do what they say. With exactly one pending trade the id can be omitted.

## Disclosure
- Network: calls `api.xstocker.com` and `xstocker.com` through `@xstocker/agent-sdk`. No other third-party services, no telemetry.
- The official SDK is **vendored unmodified** (`vendor/agent-sdk`, see `VENDORED.md`). Nothing is installed or downloaded at runtime, and the plugin never updates itself. Needs Node.js 18+ on the machine.
- Spawns a short-lived `node` process per SDK call with a fixed command line (`node sdk-bridge.js`, request as JSON on stdin). It never runs a command chosen by the model and never uses a shell.
- Writes only to `<HERMES_HOME>/plugin-data/greenlight/` (state and receipts). Reads no credentials and holds no keys.

## Development
```bash
pip install pytest fastapi httpx pyyaml
python -m pytest tests          # 21 tests, no network needed
hermes plugins validate . --install-deps
```
The tests cover approval gating, caps and limits, receipts and tamper detection, quote-drift refusal, the hooks, the slash command, the pane backend routes, demo mode and the vendored SDK. Checked against Hermes v0.23.1.

Tested on Linux with Node.js 22 and Python 3.13. Needs Node.js 18+ and Python 3.11+. The code avoids platform-specific calls, but macOS and Windows are untested.
