# Architecture

## Components
1. **Python plugin** (`__init__.py`, `schemas.py`, `tools.py`, `service.py`, `state.py`, `risk.py`, `bridge.py`)
   - `__init__.py` registers the tools, the `pre_tool_call` and `pre_llm_call` hooks, the `/greenlight` slash command and the bundled skill
   - `service.py` is the one core flow, shared by the tools, the slash command and the pane backend
   - `state.py` owns local state (proposals, caps, hash-chained receipts) under `<HERMES_HOME>/plugin-data/greenlight/`
   - `risk.py` holds the pure risk-scoring and USD-pricing functions
   - `bridge.py` calls the Node bridge for the agent SDK

2. **Node bridge** (`sdk-bridge.js`)
   - Thin wrapper around `@xstocker/agent-sdk` (pinned 1.4.0, installed on first use with scripts disabled)
   - Receives one JSON request on stdin, returns one JSON response: assets, an unsigned order, or an order status

3. **Pane backend** (`dashboard/plugin_api.py`)
   - FastAPI routes under `/api/plugins/greenlight/`: `GET /pending`, `POST /proposals/{id}/approve`, `POST /proposals/{id}/reject`, `GET /receipts`
   - Broadcasts `plugin.greenlight.proposal.created` / `.updated` so the pane refreshes at once

4. **Desktop pane** (`desktop/plugin.js`)
   - Native Hermes Desktop surface: a right-hand pane, a status-bar chip showing how many trades await approval, and an auto-opened approval tab
   - Shows quote, price, risk factors, daily cap, wallet, countdown and Approve / Reject buttons
   - After approval shows the Solana Pay link; lists recent receipts with a chain-verified indicator

5. **Bundled skill** (`skills/greenlight/SKILL.md`)
   - Instructs Hermes to always propose first and wait for explicit approval

## Data flow
User intent -> `propose_trade` (validates, checks per-trade limit, allowlist and daily cap) -> agent-sdk builds the order as the **simulation**; only the quote is kept, the transaction is discarded -> proposal stored with risk score -> Desktop pane (or `/greenlight`) shows it -> user approves -> order is **rebuilt fresh** (transactions expire in about a minute) and checked for quote drift -> unsigned transaction / solanaPayUrl released through `get_trade_status` -> receipt written. Reject writes a receipt and releases nothing.

## Approval surfaces
- Desktop pane and status-bar chip (primary)
- `/greenlight approve|reject <id>` typed by the user in the terminal or a messaging chat. Slash commands are typed by a person; the model cannot invoke them.

## Safety invariants
- No private keys ever enter the plugin.
- No unsigned transaction is stored or returned until approval.
- Optional user-set limits (daily cap counting approved plus pending, per-trade limit, asset allowlist) are checked before a proposal is created. All are off by default; the plugin imposes no amount, asset or token restrictions of its own.
- Approval is refused if the fresh quote drifted beyond `max_quote_drift_pct`.
- A `pre_tool_call` gate blocks other tools from carrying an xStocks order link that no approved proposal released.
- A `pre_llm_call` reminder tells the model which proposals are pending or approved, so it never treats an open proposal as approved.
- Receipts are hash-chained; tampering is detected by `list_receipts` and shown in the pane.
- All state is local.
