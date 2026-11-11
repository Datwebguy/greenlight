<p align="center"><img src="assets/banner.png" alt="Greenlight: explicit approval for xStocks trades inside Hermes Agent" width="100%"></p>

# Greenlight

**Explicit approval for xStocks trades inside Hermes Agent.**

![License: MIT](https://img.shields.io/badge/license-MIT-green) ![Hermes plugin](https://img.shields.io/badge/Hermes-plugin-blue) ![Non-custodial](https://img.shields.io/badge/non--custodial-no%20keys-success) ![Solana](https://img.shields.io/badge/Solana-xStocks-purple)

Greenlight turns a trade request into a simulated proposal with a risk score, surfaces it in a native Hermes Desktop pane, and releases an unsigned transaction only after you give the green light. It never holds, reads or uses a private key.

## Highlights
- **Natural-language trading.** Say "Propose buying $25 of NVDAx" and Hermes does the rest.
- **Live simulation on every proposal.** Real route, quote, price, fee and slippage from the xStocks API before you decide.
- **Transparent risk score.** A 0-100 score with its contributing factors shown next to Approve and Reject.
- **A real approval gate.** No transaction exists in local state until you approve; it is then rebuilt fresh and checked for quote drift.
- **Native approval surfaces.** Desktop pane, status-bar chip and notifications, plus `/greenlight` in the terminal and messaging chats.
- **Your guardrails, your rules.** Optional daily cap, per-trade limit, ticker allowlist and drift limit. Nothing is capped unless you say so.
- **Tamper-evident receipts.** Every decision is written to a hash-chained local log you can verify at any time.
- **Non-custodial by design.** Your wallet signs and sends. Greenlight only hands you an unsigned `solanaPayUrl`.

## Screenshots
| Approval pane | After approval |
|---|---|
| ![Approval pane with quote, risk score, daily cap and Approve / Reject](assets/screenshots/approval-pane.png) | ![Approved state with Open in wallet, Copy link and Done](assets/screenshots/approved-state.png) |

![The /greenlight slash command: status, demo, approve and receipts](assets/screenshots/slash-command.png)

*Pane images are rendered from the plugin's own `desktop/plugin.js` with live xStocks quote data; the terminal image is real `/greenlight` output.*

## Try it in 60 seconds
No wallet and no funds needed. Install, enable, then run `/greenlight demo` or click **Run demo** in the pane. You get a live NVDAx quote, a risk score and the approval pane. Approving a demo writes a real receipt and releases nothing.

| Step | What happens |
|---|---|
| 1. Propose | `propose_trade` simulates the order against the live xStocks API and keeps only the quote |
| 2. Review | The pane shows quote, price, fee, slippage, risk factors and your daily cap if you set one |
| 3. Approve | The order is rebuilt fresh, checked for quote drift, and released as an unsigned `solanaPayUrl` |
| 4. Sign | Your wallet signs and sends |
| 5. Receipt | A hash-chained receipt is written and `list_receipts` verifies the chain |

## Install
```bash
hermes plugins install https://github.com/Datwebguy/greenlight
hermes plugins enable greenlight
```
Then switch **Greenlight** on in the Desktop app under Capabilities > Plugins, and set your public wallet address as `default_wallet` on the plugin's settings page.

Requires Hermes Agent 0.21.5 or newer and Node.js 18 or newer (Python 3.11 or newer is already part of Hermes).

## Use it
Ask Hermes:
```
Propose buying $25 of NVDAx
```
Approve in the Desktop pane, or from anywhere with the slash command:

| Command | Does |
|---|---|
| `/greenlight` | Show pending trades and your cap |
| `/greenlight approve [id]` | Approve a proposal (the id can be omitted when exactly one is pending) |
| `/greenlight reject [id]` | Reject a proposal |
| `/greenlight done [id]` | Dismiss an approved proposal once you have signed |
| `/greenlight receipts` | Show recent receipts |
| `/greenlight demo` | Run the demo flow |

### Agent tools
| Tool | Purpose |
|---|---|
| `propose_trade` | Simulate a trade and create a pending proposal (never releases a transaction) |
| `get_trade_status` | Look up a proposal or an on-chain signature; the unsigned link appears only after approval |
| `list_receipts` | Recent receipts, with chain verification |

A bundled `greenlight` skill teaches the agent the flow: propose first, relay the summary, wait for approval.

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
    G-->>H: proposal + risk, no transaction
    G-->>U: Desktop pane / chip / notification
    U->>G: Approve (pane or /greenlight approve)
    G->>X: rebuild order fresh
    G-->>G: refuse release if the quote drifted
    G-->>H: get_trade_status releases solanaPayUrl
    H-->>U: link; your wallet signs and sends
    G-->>G: write hash-chained receipt
```

### Simulation
Every proposal is built against the live xStocks API through the official SDK, so you see a real route, expected output, fee and slippage before deciding. On approval the order is rebuilt, because unsigned transactions are short-lived, and release is refused if the fresh quote is worse than the one you approved by more than your drift limit.

### Risk score
A transparent 0-100 score, shown with its factors.

| Factor | Looks at |
|---|---|
| Size | Trade value relative to your daily cap (when you set one) |
| Slippage | The quote's slippage in basis points |
| Fee | Fee as a share of the trade |
| Pay token | Price exposure on SOL legs |
| Route | Availability of a Solana Pay link and block-height expiry |

## Security model
- **Non-custodial.** No private key ever enters the plugin. It never signs and never broadcasts; transactions are built by the official xStocker SDK and signed by your own wallet.
- **Approval is the gate.** Nothing transaction-shaped is stored or returned before you approve. Approval rebuilds the order, checks quote drift and opens a release window (30 minutes by default) after which the link is no longer served.
- **Defense in depth.** A `pre_llm_call` hook keeps the agent aware of which proposals are pending or approved, and a `pre_tool_call` hook stops any other tool from carrying an xStocks order link that an approved proposal did not release.
- **Tamper-evident history.** Receipts are chained with SHA-256; any edit breaks the chain and the pane and `list_receipts` show it.
- **Self-contained.** The official SDK is vendored unmodified, so there are no runtime installs, downloads or self-updates.

## Configuration
Settings live under `plugins.entries.greenlight.settings` and on the plugin's settings page in the Desktop app.

| Key | Default | Meaning |
|---|---|---|
| `default_wallet` | empty | Your public Solana address, used when a request names none |
| `daily_cap_usd` | 0 (off) | Optional cap on the USD value of approved plus pending proposals per UTC day |
| `max_trade_usd` | 0 (off) | Optional limit on any single trade |
| `allowed_assets` | empty (all) | Comma-separated tickers the plugin may propose |
| `max_quote_drift_pct` | 1.0 | Release is refused if the quote at approval is worse than the approved one by more than this |
| `proposal_ttl_minutes` | 10 | How long a pending proposal waits for your decision |
| `release_window_minutes` | 30 | How long an approved link stays available to the agent |

Any amount, any xStock the API lists and any pay token the API accepts is allowed unless you set a guardrail. When you set a cap or per-trade limit, SOL-denominated trades take an optional `max_usd` so they can be priced against it.

## Transparency
- **Network:** calls `api.xstocker.com` and `xstocker.com` through the official `@xstocker/agent-sdk`. No other third-party services and no telemetry.
- **Code:** the SDK is vendored unmodified in `vendor/agent-sdk` (integrity recorded in `VENDORED.md`). Nothing is installed or downloaded at runtime.
- **Processes:** a short-lived `node` process per SDK call with a fixed command line (`node sdk-bridge.js`, request as JSON on stdin). No shell, and never a command chosen by the model.
- **Files:** writes only to `<HERMES_HOME>/plugin-data/greenlight/` (proposals and receipts). Reads no credentials and holds no keys.

## Development
```bash
pip install pytest fastapi httpx pyyaml
python -m pytest tests                  # 29 tests, no network needed
hermes plugins validate . --install-deps
```
Validated with `hermes plugins validate` and `hermes plugins doctor` on Hermes v0.23.1. The tests cover approval gating, limits, receipts and tamper detection, quote-drift refusal, concurrency during approval, the release window, the hooks, the slash command, the pane backend and the vendored SDK.

## Links
- [xStocker Agent SDK](https://www.npmjs.com/package/@xstocker/agent-sdk)
- [xStocks docs](https://docs.xstocks.fi)
- [Hermes plugin guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md)
- [Hermes Desktop Plugin SDK](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md)

## License
MIT. See [LICENSE](LICENSE).
