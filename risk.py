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
    return None, "max_usd is required to price this trade (SOL legs have no USD quote)"


def score(notional, cap, details, pay_token, solana_pay_available):
    """Return {score 0-100, level, factors[]}. Higher is riskier."""
    factors = []
    ratio = (notional / cap) if cap else 1.0
    size_pts = min(40, round(ratio * 40))
    factors.append({"name": "size", "points": size_pts, "note": "%.0f%% of daily cap" % (ratio * 100)})

    slip = details.get("slippageBps")
    slip_pts = min(25, round((slip or 0) / 20))
    factors.append({"name": "slippage", "points": slip_pts, "note": "%s bps" % (slip if slip is not None else "n/a")})

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
    factors.append({"name": "fee", "points": fee_pts, "note": "%.2f%% of output" % fee_pct})

    sol_pts = 10 if pay_token == "SOL" else 0
    if sol_pts:
        factors.append({"name": "pay_token", "points": sol_pts, "note": "SOL leg: price exposure"})
    link_pts = 0 if solana_pay_available else 5
    if link_pts:
        factors.append({"name": "no_pay_link", "points": link_pts, "note": "no Solana Pay link available"})
    expiry_pts = 5 if details.get("lastValidBlockHeight") is None else 0
    if expiry_pts:
        factors.append({"name": "expiry", "points": expiry_pts, "note": "no block-height expiry reported"})

    total = min(100, sum(f["points"] for f in factors))
    level = "low" if total < 25 else "medium" if total < 50 else "high"
    return {"score": total, "level": level, "factors": [f for f in factors if f["points"]] or factors[:1]}
