---
name: greenlight
description: Propose xStocks trades first and wait for explicit approval in the Desktop pane before any transaction material is used.
---

# Greenlight

## Instructions for Hermes
Always use the `propose_trade` tool first. Never assume a trade is approved. Surface the Desktop pane and wait for explicit user approval before treating any transaction material as available. Prefer USDC. Summarize risk and daily remaining before asking the user to approve.

## Flow
1. User asks for a trade (for example "buy $25 of NVDAx"). Call `propose_trade`. Ask for the wallet only if no default wallet is configured.
2. Relay the `summary`: quote, risk and daily remaining. Tell the user to approve or reject in the Greenlight pane (or type `/greenlight approve`).
3. Call `get_trade_status` with the `proposal_id`. Only when `status` is `approved` does it include `solanaPayUrl` or `transaction`. Hand the link to the user; their wallet signs. Never sign or broadcast.
4. If the status is `rejected` or `expired`, stop and say so. Do not retry the same trade without the user asking.
5. After the user signs, pass the signature to `get_trade_status` to confirm it landed. Use `list_receipts` to show history.
