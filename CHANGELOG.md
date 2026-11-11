# Changelog

## 0.1.0
- Initial release: `propose_trade`, `get_trade_status` and `list_receipts` tools.
- Live simulation through the vendored official `@xstocker/agent-sdk` 1.4.0.
- Native Desktop approval pane, status-bar chip and notifications.
- `/greenlight` slash command (status, approve, reject, done, receipts, demo).
- `pre_tool_call` approval gate and `pre_llm_call` pending-proposal reminder.
- Optional guardrails: daily cap, per-trade limit, allowed tickers, quote-drift limit, release window.
- Hash-chained local receipts with tamper detection.
- No-wallet demo mode.
