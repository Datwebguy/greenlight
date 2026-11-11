"""Tool schemas: what the model sees."""

PROPOSE_TRADE = {
    "name": "propose_trade",
    "description": (
        "Propose an xStocks trade (always call this first; never ask for or assume approval yourself). Runs in simulation mode first. Returns quote, risk score, "
        "daily cap status, and a pending proposal ID. Does not execute or return a signed transaction. "
        "The user must approve in the Desktop pane before any unsigned transaction is released."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "xStocks ticker (e.g. NVDAx, AAPLx) or mint address."},
            "amount": {"type": "number", "description": "Amount to trade."},
            "side": {"type": "string", "enum": ["buy", "sell"]},
            "pay_token": {"type": "string", "enum": ["USDC", "SOL"], "default": "USDC"},
            "wallet": {"type": "string", "description": "User's Solana wallet address. Optional when the user has configured a default wallet; otherwise ask the user for it."},
            "max_usd": {"type": "number", "description": "Optional hard cap in USD for this single trade."},
        },
        "required": ["asset", "amount", "side"],
    },
}

GET_TRADE_STATUS = {
    "name": "get_trade_status",
    "description": (
        "Look up a local Greenlight proposal by proposal_id (pending, approved, rejected or expired; the "
        "unsigned transaction or solanaPayUrl is included only once approved), or look up a broadcast "
        "transaction by signature. Never assume a trade is approved: call this and check status."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "proposal_id": {"type": "string", "description": "Proposal ID returned by propose_trade."},
            "signature": {"type": "string", "description": "Solana transaction signature to check on-chain."},
        },
    },
}

LIST_RECEIPTS = {
    "name": "list_receipts",
    "description": "Return recent local Greenlight receipts (approvals, rejections, expiries, settlements), newest first.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max receipts to return (default 10, max 100)."},
            "proposal_id": {"type": "string", "description": "Only receipts for this proposal."},
        },
    },
}
