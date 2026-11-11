## What it does
Greenlight adds explicit green-light approval for xStocks trades on Solana. `propose_trade` simulates an order against the live xStocks API through the official `@xstocker/agent-sdk` and returns a quote, a 0-100 risk score with its factors and the remaining daily cap, but never a transaction. The user approves or rejects in a native Desktop approval pane; only then does `get_trade_status` release an unsigned transaction or Solana Pay link, rebuilt fresh and refused if the quote drifted. Non-custodial: it never holds, reads or signs with a private key and never broadcasts.

Repo: https://github.com/Datwebguy/greenlight (pinned at `dce8cb8cc813dd912bba4a7413eb7d8d200af5a1`)

## Hermes surfaces used
- Tools: `propose_trade`, `get_trade_status`, `list_receipts`
- Hooks: `pre_tool_call` (approval gate) and `pre_llm_call` (keeps the agent aware of pending proposals)
- Slash command: `/greenlight` (status, approve, reject, done, receipts, demo)
- Desktop Plugin SDK: approval pane, status-bar chip, notifications
- Bundled skill: `greenlight`
- Plugin settings (`config_schema`) and a pane backend (`dashboard/plugin_api.py`)

## Disclosure
- Network: calls `api.xstocker.com` and `xstocker.com` through the official SDK. No other third-party services, no telemetry.
- Code: the SDK is vendored unmodified in `vendor/agent-sdk` (npm tarball sha1 and integrity recorded in `VENDORED.md`). Nothing is installed or downloaded at runtime and the plugin never updates itself.
- Processes: a short-lived `node` process per SDK call with a fixed command line (`node sdk-bridge.js`, request as JSON on stdin). No shell, and never a command chosen by the model.
- Files: writes proposals and receipts only to `<HERMES_HOME>/plugin-data/greenlight/`. Reads no credentials and holds no keys.
- No Python dependencies. Needs Node.js 18+.

## Testing evidence
- `hermes plugins validate . --install-deps` passes on Hermes v0.23.1, and `hermes plugins doctor . --ci` passes.
- `scripts/validate_plugin_catalog.py` passes on this entry.
- 29 automated tests (`python -m pytest tests`) cover approval gating, limits, receipts and tamper detection, quote-drift refusal, concurrent approve/reject, the release window, both hooks, the slash command, the pane backend, demo mode and the vendored SDK.
- Installed from git with `hermes plugins install` and enabled; tools, both hooks and `/greenlight` exercised through Hermes' own registry against the live xStocks API (propose, approve, receipt).
- No-wallet demo: `/greenlight demo`.

## Checklist
- [x] Read the contributing and catalog submission guides
- [x] Searched for duplicate PRs
- [x] Change limited to one file: `plugin-catalog/greenlight.yaml`
- [x] `hermes plugins validate` run
- [x] Documentation provided (README)
- [ ] Screenshots of the approval pane (add from a Desktop install)
