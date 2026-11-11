"""Local state: proposals, daily-cap accounting and a hash-chained receipt log.

Everything lives in one JSON file under the plugin data directory. Nothing here
ever holds or reads a private key.
"""

import contextlib
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # POSIX advisory locking; best effort elsewhere
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

_LOCK = threading.RLock()
_GETTER = None
ZERO_HASH = "0" * 64

DEFAULTS = {"daily_cap_usd": 250.0, "proposal_ttl_minutes": 10, "max_quote_drift_pct": 1.0}


def data_dir():
    override = os.environ.get("GREENLIGHT_DATA_DIR")
    if override:
        return Path(override)
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "plugin-data" / "greenlight"


def configure(getter):
    """Register a callable(key, default) that reads this plugin's settings."""
    global _GETTER
    _GETTER = getter


def setting(key, default=None):
    default = DEFAULTS.get(key, default) if default is None else default
    value = None
    if _GETTER is not None:
        try:
            value = _GETTER(key, None)
        except Exception:
            value = None
    if value is None:
        try:
            from hermes_cli.config import load_config_readonly

            cfg = load_config_readonly() or {}
            value = (((cfg.get("plugins") or {}).get("entries") or {}).get("greenlight") or {}).get("settings", {}).get(key)
        except Exception:
            value = None
    if value is None:
        value = os.environ.get("GREENLIGHT_" + key.upper())
    if value is None:
        return default
    try:
        return type(default)(value)
    except (TypeError, ValueError):
        return default


def _empty():
    return {"version": 1, "proposals": {}, "receipts": []}


@contextlib.contextmanager
def transaction(write=True):
    with _LOCK:
        d = data_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / ".lock", "a+") as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                path = d / "state.json"
                try:
                    st = json.loads(path.read_text())
                except (FileNotFoundError, ValueError):
                    st = _empty()
                st.setdefault("proposals", {})
                st.setdefault("receipts", [])
                yield st
                if write:
                    tmp = path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(st, indent=2, sort_keys=True))
                    os.replace(tmp, path)
            finally:
                if fcntl:
                    fcntl.flock(lock, fcntl.LOCK_UN)


def now():
    return time.time()


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- receipts

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _receipt_hash(prev, body):
    return hashlib.sha256((prev + _canonical(body)).encode()).hexdigest()


def append_receipt(st, proposal_id, event, data=None):
    prev = st["receipts"][-1]["hash"] if st["receipts"] else ZERO_HASH
    body = {
        "id": "rc_%04d" % (len(st["receipts"]) + 1),
        "ts": iso(now()),
        "proposal_id": proposal_id,
        "event": event,
        "data": data or {},
    }
    receipt = dict(body, prev_hash=prev, hash=_receipt_hash(prev, body))
    st["receipts"].append(receipt)
    return receipt


def verify_chain(receipts):
    prev = ZERO_HASH
    for r in receipts:
        body = {k: r.get(k) for k in ("id", "ts", "proposal_id", "event", "data")}
        if r.get("prev_hash") != prev or r.get("hash") != _receipt_hash(prev, body):
            return False
        prev = r["hash"]
    return True


# -------------------------------------------------------------- accounting

def expire_stale(st):
    t = now()
    for p in st["proposals"].values():
        if p["status"] == "pending" and p["expires_at_ts"] <= t:
            p["status"] = "expired"
            append_receipt(st, p["id"], "expired", {"notional_usd": p["notional_usd"]})


def daily_used(st):
    t = now()
    today = utc_day(t)
    used = 0.0
    for p in st["proposals"].values():
        if p["status"] == "approved" and utc_day(p.get("approved_at_ts", 0)) == today:
            used += p["notional_usd"]
        elif p["status"] == "pending" and p["expires_at_ts"] > t:
            used += p["notional_usd"]
    return used


def cap_snapshot(st):
    cap = float(setting("daily_cap_usd"))
    used = daily_used(st)
    return {"limit_usd": cap, "used_usd": round(used, 2), "remaining_usd": round(max(cap - used, 0.0), 2)}
