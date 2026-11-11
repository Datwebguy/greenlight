"""Greenlight core flow, shared by the model-facing tools and the Desktop pane backend.

Invariants:
  * no unsigned transaction / solanaPayUrl is stored or returned before approval;
  * the daily cap is checked before a proposal is created;
  * approval rebuilds the order fresh and refuses release if the quote drifted;
  * every decision writes a hash-chained local receipt.
"""

import hashlib
import re
import time
import uuid

from . import bridge, risk, state

_B58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TICKER = re.compile(r"^[A-Za-z0-9]{1,12}$")
PAY_URL = re.compile(r"solana:https%3A%2F%2Fxstocker\.com[^\s\"'\\]*")
TX_MAX_AGE = 50  # seconds; unsigned transactions expire after roughly a minute

_assets_cache = {"ts": 0.0, "data": None}


class GreenlightError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def _err(code, message, **extra):
    return dict(extra, status="error", error=code, message=message)


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest() if text else None


def _notify(event, payload):
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event

        broadcast_plugin_event("greenlight", event, payload)
    except Exception:
        pass


def _resolve_asset(asset):
    if time.time() - _assets_cache["ts"] > 600 or not _assets_cache["data"]:
        _assets_cache["data"] = bridge.get_assets()
        _assets_cache["ts"] = time.time()
    want = asset.strip().lower()
    for a in _assets_cache["data"].get("assets", []):
        sym = a["symbol"].lower()
        if want in (sym, sym.rstrip("x"), a["mint"].lower()):
            return a["symbol"]
    known = ", ".join(a["symbol"] for a in _assets_cache["data"].get("assets", [])[:25])
    raise GreenlightError("unknown_asset", "Unknown xStock '%s'. Known: %s" % (asset, known))


def _validate(args):
    asset = str(args.get("asset") or "").strip()
    if not (_TICKER.match(asset) or _B58.match(asset)):
        raise GreenlightError("invalid_asset", "asset must be an xStocks ticker (e.g. NVDAx) or mint address")
    try:
        amount = float(args.get("amount"))
    except (TypeError, ValueError):
        raise GreenlightError("invalid_amount", "amount must be a number")
    if not (amount > 0) or amount != amount or amount == float("inf"):
        raise GreenlightError("invalid_amount", "amount must be a positive, finite number")
    side = args.get("side")
    if side not in ("buy", "sell"):
        raise GreenlightError("invalid_side", "side must be 'buy' or 'sell'")
    pay_token = str(args.get("pay_token") or "USDC").strip().upper()
    if not pay_token.isalnum():
        raise GreenlightError("invalid_pay_token", "pay_token must be a token symbol such as USDC or SOL")
    wallet = str(args.get("wallet") or "").strip() or str(state.setting("default_wallet") or "").strip()
    if not wallet:
        raise GreenlightError("wallet_required", "Ask the user for their Solana wallet address (or set default_wallet)")
    if not _B58.match(wallet):
        raise GreenlightError("invalid_wallet", "wallet must be a base58 Solana address")
    max_usd = args.get("max_usd")
    if max_usd is not None:
        try:
            max_usd = float(max_usd)
        except (TypeError, ValueError):
            raise GreenlightError("invalid_max_usd", "max_usd must be a number")
        if not (max_usd > 0):
            raise GreenlightError("invalid_max_usd", "max_usd must be positive")
    return asset, amount, side, pay_token, wallet, max_usd


def _public(p, st=None):
    """Proposal view that never contains transaction material (see _release_view)."""
    keys = ("id", "status", "asset", "side", "amount", "pay_token", "wallet", "quote", "notional_usd",
            "risk", "cap", "unpriced", "created_at", "expires_at", "approved_at", "rejected_at", "signature", "settlement")
    view = {k: p[k] for k in keys if k in p}
    view["implied_price_usd"] = _implied_price(p["quote"])
    view["seconds_left"] = max(0, int(p["expires_at_ts"] - time.time())) if p["status"] == "pending" else 0
    return view


# ------------------------------------------------------------------ propose

def propose_trade(args):
    asset, amount, side, pay_token, wallet, max_usd = _validate(args)
    symbol = _resolve_asset(asset)
    # Accepted pay tokens come from the live API, not a hardcoded list.
    accepted = [t["symbol"].upper() for t in (_assets_cache["data"] or {}).get("payTokens", [])]
    if accepted and pay_token not in accepted:
        raise GreenlightError("invalid_pay_token", "pay_token must be one of: %s" % ", ".join(accepted))
    allowed = [a.strip().lower() for a in str(state.setting("allowed_assets") or "").split(",") if a.strip()]
    if allowed and symbol.lower().rstrip("x") not in [a.rstrip("x") for a in allowed]:
        raise GreenlightError("asset_not_allowed", "%s is not in the allowed_assets list" % symbol)

    # Mandatory simulation: build the order against the live API to get a real
    # route, quote, fee and slippage. The unsigned transaction is discarded here.
    order = bridge.build_order(wallet, symbol, amount, side, pay_token)
    details = order.get("details") or {}
    has_link = bool(order.get("solanaPayUrl"))

    notional, why = risk.notional_usd(side, pay_token, amount, details, max_usd)
    per_trade = float(state.setting("max_trade_usd"))
    limits_on = per_trade > 0 or float(state.setting("daily_cap_usd")) > 0
    unpriced = notional is None
    if unpriced:
        if limits_on:  # a limit is configured, so the trade must be priced to be checked against it
            raise GreenlightError("max_usd_required", why)
        notional = 0.0  # no limits set: nothing to enforce, the trade is simply not priced in USD
    if per_trade > 0 and notional > per_trade + 1e-9:
        raise GreenlightError("over_trade_limit", "Trade value $%.2f exceeds the per-trade limit $%.2f" % (notional, per_trade))
    if max_usd and notional > max_usd + 1e-9:
        raise GreenlightError("over_trade_limit", "Trade value $%.2f exceeds max_usd $%.2f" % (notional, max_usd))

    with state.transaction() as st:
        state.expire_stale(st)
        cap = state.cap_snapshot(st)
        if cap["remaining_usd"] is not None and notional > cap["remaining_usd"] + 1e-9:
            return {"status": "rejected", "reason": "daily_cap_exceeded", "notional_usd": round(notional, 2),
                    "cap": cap, "message": "This trade would exceed the local daily cap. No proposal was created."}
        scored = risk.score(notional, cap["limit_usd"], details, pay_token, has_link)
        remaining_after = None if cap["remaining_usd"] is None else round(cap["remaining_usd"] - notional, 2)
        t = state.now()
        pid = "gl_" + uuid.uuid4().hex[:8]
        ttl = int(state.setting("proposal_ttl_minutes")) * 60
        st["proposals"][pid] = {
            "id": pid, "status": "pending", "asset": symbol, "side": side, "amount": amount,
            "pay_token": pay_token, "wallet": wallet, "quote": details, "notional_usd": round(notional, 2),
            "risk": scored, "created_at": state.iso(t), "created_at_ts": t,
            "expires_at": state.iso(t + ttl), "expires_at_ts": t + ttl,
            "unpriced": unpriced,
            "cap": {"limit_usd": cap["limit_usd"], "used_usd": cap["used_usd"], "remaining_after_usd": remaining_after},
        }
        proposal = _public(st["proposals"][pid])
    _notify("proposal.created", {"id": pid})
    return {
        "status": "pending_approval", "proposal_id": pid, "summary": _summary(proposal), "quote": details, "risk": scored,
        "notional_usd": None if unpriced else round(notional, 2),
        "daily_remaining_usd": proposal["cap"]["remaining_after_usd"],
        "cap": proposal["cap"], "expires_at": proposal["expires_at"],
        "next": "Ask the user to approve or reject proposal %s in the Greenlight Desktop pane, then call "
                "get_trade_status. No transaction has been released." % pid,
    }


def _summary(p):
    q = p["quote"]
    price = _implied_price(q)
    cap = p["cap"]
    cap_text = ("$%.2f of the $%.2f daily cap remains" % (cap["remaining_after_usd"], cap["limit_usd"])
                if cap["limit_usd"] is not None else "no daily cap is set")
    return ("%s %s: pay %s, receive about %s%s. Risk %s/100 (%s); %s. "
            "Waiting for the user to approve in Greenlight." % (
                p["side"].upper(), p["asset"], q.get("amountIn"), q.get("expectedOut"),
                (" (~$%.2f each)" % price) if price else "", p["risk"]["score"], p["risk"]["level"], cap_text))


def _implied_price(q):
    spent, su = risk.parse_amount(q.get("amountIn"))
    got, gu = risk.parse_amount(q.get("expectedOut"))
    if spent and got and su == "USDC" and gu != "USDC":
        return spent / got
    if spent and got and gu == "USDC" and su != "USDC":
        return got / spent
    return None


# ------------------------------------------------------- approve / reject

def approve(proposal_id):
    with state.transaction() as st:
        state.expire_stale(st)
        p = st["proposals"].get(proposal_id)
        if not p:
            raise GreenlightError("not_found", "No such proposal")
        if p["status"] != "pending":
            raise GreenlightError("not_pending", "Proposal is %s" % p["status"])
        # Rebuild right before release: unsigned transactions expire in ~1 minute.
        order = bridge.build_order(p["wallet"], p["asset"], p["amount"], p["side"], p["pay_token"])
        drift = _quote_drift_pct(p["quote"], order.get("details") or {})
        limit = float(state.setting("max_quote_drift_pct"))
        if drift > limit:
            p["drift_pct"] = round(drift, 3)
            raise GreenlightError("quote_drifted", "Quote moved %.2f%% against you (limit %.2f%%). Reject and "
                                  "propose again." % (drift, limit), fresh_quote=order.get("details"))
        t = state.now()
        p["status"] = "approved"
        p["approved_at"], p["approved_at_ts"] = state.iso(t), t
        p["release"] = {"transaction": order.get("transaction"), "solanaPayUrl": order.get("solanaPayUrl"),
                        "built_at_ts": t}
        state.append_receipt(st, p["id"], "approved", {
            "asset": p["asset"], "side": p["side"], "amount": p["amount"], "notional_usd": p["notional_usd"],
            "quote": p["quote"], "risk": p["risk"]["score"],
            "release_sha256": {"transaction": _digest(order.get("transaction")),
                               "solanaPayUrl": _digest(order.get("solanaPayUrl"))},
        })
        return _release_view(p)


def reject(proposal_id):
    with state.transaction() as st:
        state.expire_stale(st)
        p = st["proposals"].get(proposal_id)
        if not p:
            raise GreenlightError("not_found", "No such proposal")
        if p["status"] != "pending":
            raise GreenlightError("not_pending", "Proposal is %s" % p["status"])
        p["status"] = "rejected"
        p["rejected_at"] = state.iso(state.now())
        state.append_receipt(st, p["id"], "rejected", {"asset": p["asset"], "side": p["side"],
                                                       "notional_usd": p["notional_usd"]})
        return _public(p)


def _quote_drift_pct(approved, fresh):
    a, _ = risk.parse_amount(approved.get("expectedOut"))
    f, _ = risk.parse_amount(fresh.get("expectedOut"))
    if not a or f is None:
        return 0.0
    return max(0.0, (a - f) / a * 100)


def _release_view(p):
    """The ONLY place transaction material leaves local state, and only for approved proposals."""
    view = _public(p)
    if p["status"] == "approved":
        rel = p.get("release") or {}
        view["solanaPayUrl"] = rel.get("solanaPayUrl")
        view["transaction"] = rel.get("transaction")
        view["note"] = ("Unsigned. Prefer solanaPayUrl: the user's wallet fetches a fresh transaction when they "
                        "sign. Greenlight never signs or broadcasts.")
    return view


# ------------------------------------------------------------ status / lists

def get_trade_status(args):
    pid = (args.get("proposal_id") or "").strip()
    sig = (args.get("signature") or "").strip()
    if not pid and not sig:
        raise GreenlightError("missing_argument", "Provide proposal_id or signature")
    out = {}
    if pid:
        with state.transaction() as st:
            state.expire_stale(st)
            p = st["proposals"].get(pid)
            if not p:
                raise GreenlightError("not_found", "No such proposal")
            if p["status"] == "approved" and not p.get("signature"):
                rel = p.get("release") or {}
                if time.time() - rel.get("built_at_ts", 0) > TX_MAX_AGE:
                    order = bridge.build_order(p["wallet"], p["asset"], p["amount"], p["side"], p["pay_token"])
                    rel.update(transaction=order.get("transaction"), solanaPayUrl=order.get("solanaPayUrl"),
                               built_at_ts=time.time())
                    p["release"] = rel
            out = _release_view(p)
    if sig:
        chain = bridge.order_status(sig)
        out["signature_status"] = chain
        if pid and chain.get("status") in ("confirmed", "finalized"):
            with state.transaction() as st:
                p = st["proposals"].get(pid)
                if p and p["status"] == "approved" and not p.get("signature"):
                    p["signature"] = sig
                    p["settlement"] = chain["status"]
                    state.append_receipt(st, pid, "settled", {"signature": sig, "status": chain["status"]})
                    out["settlement"] = chain["status"]
    return out


def pending():
    with state.transaction() as st:
        state.expire_stale(st)
        items = [_public(p) for p in st["proposals"].values() if p["status"] == "pending"]
        recent = [_release_view(p) for p in sorted(st["proposals"].values(), key=lambda x: -x["created_at_ts"])
                  if p["status"] in ("approved",) and not p.get("signature")][:3]
        cap = state.cap_snapshot(st)
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"pending": items, "approved": recent, "cap": cap}


def list_receipts(limit=10, proposal_id=None):
    limit = max(1, min(int(limit or 10), 100))
    with state.transaction(write=False) as st:
        chain_ok = state.verify_chain(st["receipts"])
        items = [r for r in st["receipts"] if not proposal_id or r["proposal_id"] == proposal_id]
    return {"receipts": list(reversed(items))[:limit], "chain_ok": chain_ok, "total": len(items)}


# -------------------------------------------------------------- gating hook

def gate_check(tool_name, args):
    """pre_tool_call gate: other tools may not carry xStocker Solana Pay material that is not a currently
    approved Greenlight release. Returns a block message or None."""
    if tool_name in ("propose_trade", "get_trade_status", "list_receipts"):
        return None
    try:
        import json

        blob = json.dumps(args, default=str)
    except Exception:
        return None
    urls = PAY_URL.findall(blob)
    if not urls:
        return None
    with state.transaction(write=False) as st:
        ok = {_digest(p.get("release", {}).get("solanaPayUrl")) for p in st["proposals"].values()
              if p["status"] == "approved" and not p.get("signature")}
    for u in urls:
        if _digest(u) not in ok:
            return ("Blocked by Greenlight: this xStocks order link was not released by an approved Greenlight "
                    "proposal. Call propose_trade and get the user's approval first.")
    return None


# ------------------------------------------------------------ llm context

def llm_context():
    """pre_llm_call reminder so the model never treats an open proposal as approved."""
    with state.transaction(write=False) as st:
        now = state.now()
        pend = [p for p in st["proposals"].values() if p["status"] == "pending" and p["expires_at_ts"] > now]
        appr = [p for p in st["proposals"].values() if p["status"] == "approved" and not p.get("signature")]
    lines = []
    for p in pend:
        lines.append("Proposal %s (%s %s $%.2f) is PENDING the user's approval. It is not approved; do not treat any "
                     "transaction as available." % (p["id"], p["side"], p["asset"], p["notional_usd"]))
    for p in appr:
        lines.append("Proposal %s was approved by the user; call get_trade_status to fetch the unsigned "
                     "transaction/solanaPayUrl for their wallet." % p["id"])
    return "Greenlight:\n" + "\n".join(lines) if lines else None


# ---------------------------------------------------------- slash command

def slash(raw):
    """/greenlight [status|approve [id]|reject [id]|receipts|cap]: human-typed approval for non-Desktop surfaces."""
    parts = (raw or "").split()
    verb = parts[0].lower() if parts else "status"
    pid = parts[1] if len(parts) > 1 else None
    try:
        if verb in ("approve", "reject"):
            if not pid:
                items = pending()["pending"]
                if len(items) != 1:
                    return "Give a proposal id: /greenlight %s <id> (%d pending)." % (verb, len(items))
                pid = items[0]["id"]
            if verb == "reject":
                reject(pid)
                return "Rejected %s. Nothing was released." % pid
            r = approve(pid)
            return ("Approved %s. Open this link in your wallet to sign (Greenlight never signs):\n%s"
                    % (pid, r.get("solanaPayUrl") or "(no link; ask the agent for the unsigned transaction)"))
        if verb == "receipts":
            rc = list_receipts(5)
            return "\n".join("%s %s %s" % (r["ts"], r["event"], r["proposal_id"]) for r in rc["receipts"]) or "No receipts yet."
        data = pending()
        c = data["cap"]
        lines = ["Daily cap: $%.2f used of $%.2f." % (c["used_usd"], c["limit_usd"]) if c["limit_usd"] is not None
                 else "No daily cap set ($%.2f approved or pending today)." % c["used_usd"]]
        for p in data["pending"]:
            q = p["quote"]
            lines.append("%s  %s %s  pay %s -> %s  risk %s/%s  %ss left" % (
                p["id"], p["side"], p["asset"], q.get("amountIn"), q.get("expectedOut"),
                p["risk"]["score"], p["risk"]["level"], p["seconds_left"]))
        if not data["pending"]:
            lines.append("No trades waiting.")
        else:
            lines.append("Use /greenlight approve <id> or /greenlight reject <id>.")
        return "\n".join(lines)
    except GreenlightError as e:
        return "Greenlight: %s" % e.message
    except bridge.BridgeError as e:
        return "Greenlight: %s" % e.message
    except Exception as e:  # never raise out of a command
        return "Greenlight error: %s" % e
