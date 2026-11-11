"""Simulation helpers and risk scoring (pure functions, no I/O)."""

import re

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def parse_amount(text):
    """'0.470123 NVDAx' -> (0.470123, 'NVDAx'); returns (None, None) if unparseable."""
    if text is None:
        return None, None
    m = _NUM.search(str(text))
    if not m:
        return None, None
    rest = str(text)[m.end():].strip()
    return float(m.group()), (rest.split()[0] if rest else None)


def notional_usd(side, pay_token, amount, details, max_usd):
    """USD value of a trade for cap accounting, or (None, reason) if it cannot be derived."""
    if pay_token == "USDC":
        if side == "buy":
            return float(amount), None
        out, unit = parse_amount(details.get("expectedOut"))
        if out is not None and unit and unit.upper() == "USDC":
            return out, None
    if max_usd:
        return float(max_usd), None
    return None, "To check this trade against your limits, please say roughly how much it is worth in dollars."


def score(notional, cap, details, pay_token, solana_pay_available):
    """Return {score 0-100, level, factors[]}. Higher is riskier."""
    factors = []
    if cap:
        ratio = notional / cap
        factors.append({"name": "size", "label": "Trade size", "points": min(40, round(ratio * 40)),
                        "note": "%.0f%% of your daily limit" % (ratio * 100)})
    else:
        factors.append({"name": "size", "label": "Trade size", "points": 0, "note": "no daily limit set"})

    slip = details.get("slippageBps")
    slip_pts = min(25, round((slip or 0) / 20))
    factors.append({"name": "slippage", "label": "Price movement allowed", "points": slip_pts,
                    "note": ("%.2f%%" % (slip / 100.0)) if slip is not None else "not reported"})

    fee, fee_unit = parse_amount(details.get("fee"))
    out, out_unit = parse_amount(details.get("expectedOut"))
    spent, spent_unit = parse_amount(details.get("amountIn"))
    fee_pct = 0.0
    if fee is not None:
        if out and fee_unit == out_unit:
            fee_pct = fee / (out + fee) * 100
        elif spent and fee_unit == spent_unit:
            fee_pct = fee / spent * 100
    fee_pts = min(15, round(fee_pct * 10))
    factors.append({"name": "fee", "label": "Fees", "points": fee_pts, "note": "%.2f%% of what you get" % fee_pct})

    sol_pts = 10 if pay_token == "SOL" else 0
    if sol_pts:
        factors.append({"name": "pay_token", "label": "Paying with SOL", "points": sol_pts,
                        "note": "its price can change while you decide"})
    link_pts = 0 if solana_pay_available else 5
    if link_pts:
        factors.append({"name": "no_pay_link", "label": "Wallet link", "points": link_pts,
                        "note": "no one-tap wallet link was available"})
    expiry_pts = 5 if details.get("lastValidBlockHeight") is None else 0
    if expiry_pts:
        factors.append({"name": "expiry", "label": "Timing", "points": expiry_pts, "note": "no expiry time was reported"})

    total = min(100, sum(f["points"] for f in factors))
    level = "low" if total < 25 else "medium" if total < 50 else "high"
    return {"score": total, "level": level, "factors": [f for f in factors if f["points"]] or factors[:1]}
