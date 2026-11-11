"""Python side of the Node bridge to the vendored official @xstocker/agent-sdk.

Spawns `node sdk-bridge.js` per call with a fixed argv and the request as JSON on stdin. Nothing is
installed or downloaded: the SDK is vendored unmodified under vendor/agent-sdk.
"""

import json
import shutil
import subprocess
from pathlib import Path

BRIDGE = Path(__file__).parent / "sdk-bridge.js"


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def call(op, payload=None, timeout=45):
    node = shutil.which("node")
    if not node:
        raise BridgeError("node_missing", "Greenlight needs Node.js 18 or newer installed to fetch live prices.")
    req = dict(payload or {}, op=op)
    try:
        proc = subprocess.run(
            [node, str(BRIDGE)], input=json.dumps(req), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise BridgeError("timeout", "The xStocks service took too long to answer. Please try again.")
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise BridgeError("bridge_error", "Couldn't get a price from the xStocks service. Please try again.")
    if not out.get("ok"):
        err = out.get("error") or {}
        msg = str(err.get("message", ""))
        if "429" in msg or "rate" in msg.lower() or "too many" in msg.lower():
            raise BridgeError("busy", "The price service is busy right now. Please try again in a moment.")
        raise BridgeError(err.get("code", "bridge_error"),
                          "The xStocks service couldn't prepare this trade: %s" % (msg or "something went wrong"))
    return out["result"]


def get_assets():
    return call("assets")


def build_order(wallet, asset, amount, side, pay_token):
    return call("buildOrder", {"wallet": wallet, "asset": asset, "amount": amount, "side": side, "payToken": pay_token})


def order_status(signature):
    return call("orderStatus", {"signature": signature})
