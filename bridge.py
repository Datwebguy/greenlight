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
        raise BridgeError("node_missing", "Node.js >= 18 is required for the xStocks SDK bridge")
    req = dict(payload or {}, op=op)
    try:
        proc = subprocess.run(
            [node, str(BRIDGE)], input=json.dumps(req), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise BridgeError("timeout", "xStocks SDK call timed out")
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise BridgeError("bridge_error", (proc.stderr or "bridge returned no JSON")[-400:])
    if not out.get("ok"):
        err = out.get("error") or {}
        raise BridgeError(err.get("code", "bridge_error"), err.get("message", "unknown bridge error"))
    return out["result"]


def get_assets():
    return call("assets")


def build_order(wallet, asset, amount, side, pay_token):
    return call("buildOrder", {"wallet": wallet, "asset": asset, "amount": amount, "side": side, "payToken": pay_token})


def order_status(signature):
    return call("orderStatus", {"signature": signature})
