# Tools

### propose_trade
Creates a pending proposal. Returns quote, risk score, daily remaining, proposal ID. Does not release any unsigned transaction.

Schema:
```json
{
  "name": "propose_trade",
  "description": "Propose an xStocks trade (always call this first; never ask for or assume approval yourself). Runs in simulation mode first. Returns quote, risk score, daily cap status, and a pending proposal ID. Does not execute or return a signed transaction. The user must approve in the Desktop pane before any unsigned transaction is released.",
  "parameters": {
    "type": "object",
    "properties": {
      "asset": {"type": "string", "description": "xStocks ticker (e.g. NVDAx, AAPLx) or mint address."},
      "amount": {"type": "number", "description": "Amount to trade."},
      "side": {"type": "string", "enum": ["buy", "sell"]},
      "pay_token": {"type": "string", "enum": ["USDC", "SOL"], "default": "USDC"},
      "wallet": {"type": "string", "description": "User's Solana wallet address. Optional when the user has configured a default wallet; otherwise ask the user for it."},
      "max_usd": {"type": "number", "description": "Optional hard cap in USD for this single trade."}
    },
    "required": ["asset", "amount", "side"]
  }
}
```

### get_trade_status
Looks up a local proposal by `proposal_id` or a broadcast transaction by `signature`. The unsigned transaction and `solanaPayUrl` appear only when the proposal is approved.

### list_receipts
Returns recent local receipts.

Handlers must always return `json.dumps(...)` and never raise.
