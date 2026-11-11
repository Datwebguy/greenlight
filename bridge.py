"""Python side of the Node bridge to @xstocker/agent-sdk.

Spawns `node sdk-bridge.js` per call. On first use the pinned SDK version is
installed (scripts disabled) into the plugin data directory.
"""

import json
import shutil
import subprocess
from pathlib import Path

from . import state

SDK_SPEC = "@xstocker/agent-sdk@1.4.0"
BRIDGE = Path(__file__).parent / "sdk-bridge.js"


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _sdk_dir():
    return state.data_dir() / "node"


def ensure_sdk():
    sdk_dir = _sdk_dir()
    if (sdk_dir / "node_modules" / "@xstocker" / "agent-sdk" / "package.json").exists():
        return sdk_dir
    npm = shutil.which("npm")
    if not npm:
        raise BridgeError("npm_missing", "npm is required once to install @xstocker/agent-sdk")
    sdk_dir.mkdir(parents=True, exist_ok=True)
    (sdk_dir / "package.json").write_text('{"name": "greenlight-sdk-cache", "private": true}')
    proc = subprocess.run(
        [npm, "install", SDK_SPEC, "--ignore-scripts", "--no-audit", "--no-fund", "--save-exact"],
        cwd=str(sdk_dir), capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise BridgeError("sdk_install_failed", (proc.stderr or proc.stdout or "npm install failed")[-400:])
    return sdk_dir


def call(op, payload=None, timeout=45):
    node = shutil.which("node")
    if not node:
        raise BridgeError("node_missing", "Node.js >= 18 is required for the xStocks SDK bridge")
    req = dict(payload or {}, op=op, sdkDir=str(ensure_sdk()))
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
