"""Talks to the xStocks service.

When Node.js 18+ is installed, requests go through the bundled, unmodified official @xstocker/agent-sdk
(a short-lived `node sdk-bridge.js` process with a fixed command line, request as JSON on stdin).
Without Node.js, the same three public endpoints are called directly with Python's standard library, so
nothing extra needs to be installed. Nothing is ever downloaded or installed at runtime.
"""

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BRIDGE = Path(__file__).parent / "sdk-bridge.js"
API_BASE = "https://api.xstocker.com"
ASSETS_URL = "https://xstocker.com/agent/assets.json"
RETRY_WAIT = 2.0  # seconds before the single retry when the service is busy

_node_path = {"checked": False, "path": None}


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ------------------------------------------------------------------ errors

def _friendly(code, message, status=None):
    """Turn a service error into a message a normal person can act on."""
    text = str(message or "")
    if status == 429 or "429" in text or "rate" in text.lower() or "too many" in text.lower():
        return BridgeError("busy", "The price service is busy right now. Please try again in a moment.")
    if status and status >= 500:
        return BridgeError("unavailable", "The xStocks service is having trouble right now. Please try again shortly.")
    return BridgeError(code or "bridge_error",
                       "The xStocks service couldn't prepare this trade: %s" % (text or "something went wrong"))


# -------------------------------------------------------------- node path

def _node():
    """Path to a Node.js 18+ executable, or None."""
    if not _node_path["checked"]:
        _node_path["checked"] = True
        exe = shutil.which("node")
        if exe:
            try:
                out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
                if int(out.lstrip("v").split(".")[0]) >= 18:
                    _node_path["path"] = exe
            except Exception:
                pass
    return _node_path["path"]


def _call_node(node, op, payload, timeout):
    req = dict(payload or {}, op=op)
    try:
        proc = subprocess.run([node, str(BRIDGE)], input=json.dumps(req), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BridgeError("timeout", "The xStocks service took too long to answer. Please try again.")
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise BridgeError("bridge_error", "Couldn't get a price from the xStocks service. Please try again.")
    if not out.get("ok"):
        err = out.get("error") or {}
        raise _friendly(err.get("code"), err.get("message"))
    return out["result"]


# ------------------------------------------------------------ python path

def _http(method, url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "greenlight-hermes-plugin"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BridgeError("unreachable", "Couldn't reach the xStocks service. Please check your internet connection and try again.")
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    if status >= 400:
        err = parsed if isinstance(parsed, dict) else {}
        raise _friendly(err.get("error"), err.get("message") or "request failed (%d)" % status, status)
    return parsed


def _call_python(op, payload):
    p = payload or {}
    if op == "assets":
        return _http("GET", ASSETS_URL)
    if op == "buildOrder":
        return _http("POST", API_BASE + "/agent/build-order", {
            "wallet": p["wallet"], "asset": p["asset"], "amount": p["amount"],
            "pay_token": p.get("payToken") or "USDC", "side": p.get("side") or "buy"})
    if op == "orderStatus":
        return _http("GET", API_BASE + "/agent/order/" + urllib.parse.quote(p["signature"], safe=""))
    raise BridgeError("bad_op", "Unknown request")


# ----------------------------------------------------------------- public

def call(op, payload=None, timeout=45):
    """Run one xStocks request, using the official SDK when Node.js is available. A single short retry
    covers the service being briefly busy."""
    for attempt in (1, 2):
        try:
            node = _node()
            return _call_node(node, op, payload, timeout) if node else _call_python(op, payload)
        except BridgeError as e:
            if e.code == "busy" and attempt == 1:
                time.sleep(RETRY_WAIT)
                continue
            raise


def get_assets():
    return call("assets")


def build_order(wallet, asset, amount, side, pay_token):
    return call("buildOrder", {"wallet": wallet, "asset": asset, "amount": amount, "side": side, "payToken": pay_token})


def order_status(signature):
    return call("orderStatus", {"signature": signature})
