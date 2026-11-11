# Tools

### propose_trade
Creates a pending proposal. Returns quote, risk score, daily remaining, proposal ID. Does not release any unsigned transaction.

Schema:
```json
{
  "name": "propose_trade",
  "description": "Propose an xStocks trade. Always runs in simulation mode first. Returns quote, risk score, daily cap status, and a pending proposal ID. Does not execute or return a signed transaction. The user must approve in the Desktop pane before any unsigned transaction is released.",
  "parameters": {
    "type": "object",
    "properties": {
      "asset": {"type": "string", "description": "xStocks ticker (e.g. NVDAx, AAPLx) or mint address."},
      "amount": {"type": "number", "description": "Amount to trade."},
      "side": {"type": "string", "enum": ["buy", "sell"]},
      "pay_token": {"type": "string", "enum": ["USDC", "SOL"], "default": "USDC"},
      "wallet": {"type": "string", "description": "User's Solana wallet address."},
      "max_usd": {"type": "number", "description": "Optional hard cap in USD for this single trade."}
    },
    "required": ["asset", "amount", "side", "wallet"]
  }
}
```
