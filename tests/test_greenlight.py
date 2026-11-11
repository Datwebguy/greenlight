import json

import pytest

import greenlight as gl
from greenlight import bridge, service, state, tools

WALLET = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"


class FakeSdk:
    def __init__(self):
        self.expected = "0.470123 NVDAx"
        self.calls = 0

    def call(self, op, payload=None, timeout=45):
        if op == "assets":
            return {"assets": [{"symbol": "NVDAx", "mint": "Xs" + "a" * 40}], "payTokens": []}
        if op == "buildOrder":
            self.calls += 1
            return {"status": "ready", "transaction": "TX%d" % self.calls,
                    "solanaPayUrl": "solana:https%3A%2F%2Fxstocker.com%2Fagent%2Fpay%3Fn%3D" + str(self.calls),
                    "details": {"side": payload["side"], "asset": payload["asset"],
                                "amountIn": "%s %s" % (payload["amount"], payload["payToken"]),
                                "expectedOut": self.expected, "fee": "0.001 NVDAx", "slippageBps": 50,
                                "lastValidBlockHeight": 123}}
        if op == "orderStatus":
            return {"status": "confirmed", "signature": payload["signature"], "tx": ""}
        raise AssertionError(op)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GREENLIGHT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GREENLIGHT_MAX_TRADE_USD", "0")  # per-trade limit off unless a test sets it
    fake = FakeSdk()
    monkeypatch.setattr(bridge, "call", fake.call)
    service._assets_cache.update(ts=0.0, data=None)
    state.configure(None)
    return fake


def propose(**kw):
    args = dict(asset="NVDAx", amount=25, side="buy", wallet=WALLET)
    args.update(kw)
    return json.loads(tools.propose_trade(args))


def test_propose_releases_nothing():
    out = propose()
    assert out["status"] == "pending_approval"
    blob = json.dumps(out)
    assert "TX1" not in blob and "solana:" not in blob
    assert out["cap"]["remaining_after_usd"] == 225.0
    assert out["risk"]["level"] == "low"


def test_release_only_after_approval():
    pid = propose()["proposal_id"]
    pending = json.loads(tools.get_trade_status({"proposal_id": pid}))
    assert pending["status"] == "pending" and "solanaPayUrl" not in pending
    service.approve(pid)
    done = json.loads(tools.get_trade_status({"proposal_id": pid}))
    assert done["status"] == "approved" and done["solanaPayUrl"].startswith("solana:")


def test_reject_never_releases():
    pid = propose()["proposal_id"]
    service.reject(pid)
    out = json.loads(tools.get_trade_status({"proposal_id": pid}))
    assert out["status"] == "rejected" and "solanaPayUrl" not in out and "transaction" not in out
    with pytest.raises(service.GreenlightError):
        service.approve(pid)


def test_daily_cap_enforced_and_pending_counts():
    assert propose(amount=200)["status"] == "pending_approval"
    out = propose(amount=100)
    assert out["status"] == "rejected" and out["reason"] == "daily_cap_exceeded"
    assert propose(amount=50)["status"] == "pending_approval"


def test_rejection_frees_cap():
    pid = propose(amount=200)["proposal_id"]
    service.reject(pid)
    assert propose(amount=200)["status"] == "pending_approval"


def test_quote_drift_blocks_release(env):
    pid = propose()["proposal_id"]
    env.expected = "0.40 NVDAx"
    with pytest.raises(service.GreenlightError) as e:
        service.approve(pid)
    assert e.value.code == "quote_drifted"
    assert json.loads(tools.get_trade_status({"proposal_id": pid}))["status"] == "pending"


def test_receipts_chain_and_tamper_detection(tmp_path):
    a, b = propose()["proposal_id"], propose()["proposal_id"]
    service.approve(a)
    service.reject(b)
    out = json.loads(tools.list_receipts({}))
    assert out["chain_ok"] and [r["event"] for r in out["receipts"]] == ["rejected", "approved"]
    p = tmp_path / "state.json"
    s = json.loads(p.read_text())
    s["receipts"][0]["data"]["notional_usd"] = 1
    p.write_text(json.dumps(s))
    assert json.loads(tools.list_receipts({}))["chain_ok"] is False


def test_sol_requires_max_usd():
    out = propose(pay_token="SOL")
    assert out["error"] == "max_usd_required"
    assert propose(pay_token="SOL", max_usd=40)["notional_usd"] == 40


def test_validation_and_never_raises(monkeypatch):
    assert propose(wallet="nope")["error"] == "invalid_wallet"
    assert propose(amount=-1)["error"] == "invalid_amount"
    assert propose(asset="ZZZZ")["error"] == "unknown_asset"
    monkeypatch.setattr(bridge, "call", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    service._assets_cache.update(ts=0.0, data=None)
    assert json.loads(tools.propose_trade({"asset": "NVDAx", "amount": 1, "side": "buy", "wallet": WALLET}))["status"] == "error"
    assert json.loads(tools.get_trade_status(None))["status"] == "error"


def test_gate_blocks_unapproved_links_and_allows_released():
    pid = propose()["proposal_id"]
    rogue = {"url": "solana:https%3A%2F%2Fxstocker.com%2Fagent%2Fpay%3Fx%3D1"}
    assert gl._gate("browser_navigate", rogue)["action"] == "block"
    assert gl._gate("propose_trade", rogue) is None
    url = service.approve(pid)["solanaPayUrl"]
    assert gl._gate("browser_navigate", {"url": url}) is None
    assert gl._gate("terminal", {"command": "ls"}) is None


def test_settlement_receipt():
    pid = propose()["proposal_id"]
    service.approve(pid)
    out = json.loads(tools.get_trade_status({"proposal_id": pid, "signature": "SIG"}))
    assert out["settlement"] == "confirmed"
    assert json.loads(tools.list_receipts({"proposal_id": pid}))["receipts"][0]["event"] == "settled"


def test_pane_backend_routes(env, monkeypatch):
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    root = Path(gl.__file__).parent
    spec = importlib.util.spec_from_file_location("gl_plugin_api", root / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    core = api._core()  # the pane backend loads its own copy of the package
    monkeypatch.setattr(core.bridge, "call", env.call)
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)

    pid = propose()["proposal_id"]
    body = c.get("/pending").json()
    assert body["pending"][0]["id"] == pid and "solanaPayUrl" not in json.dumps(body)
    ok = c.post("/proposals/%s/approve" % pid).json()
    assert ok["status"] == "approved" and ok["solanaPayUrl"]
    assert c.post("/proposals/%s/approve" % pid).status_code == 409
    assert c.get("/receipts").json()["chain_ok"] is True


def test_default_wallet_and_wallet_required(monkeypatch):
    out = json.loads(tools.propose_trade({"asset": "NVDAx", "amount": 25, "side": "buy"}))
    assert out["error"] == "wallet_required"
    monkeypatch.setenv("GREENLIGHT_DEFAULT_WALLET", WALLET)
    out = json.loads(tools.propose_trade({"asset": "NVDAx", "amount": 25, "side": "buy"}))
    assert out["status"] == "pending_approval" and "NVDAx" in out["summary"]


def test_per_trade_limit_and_allowlist(monkeypatch):
    monkeypatch.setenv("GREENLIGHT_MAX_TRADE_USD", "100")
    assert propose(amount=150)["error"] == "over_trade_limit"
    monkeypatch.setenv("GREENLIGHT_ALLOWED_ASSETS", "AAPLx")
    assert propose()["error"] == "asset_not_allowed"


def test_llm_context_tracks_state():
    assert gl._llm_context() is None
    pid = propose()["proposal_id"]
    assert pid in gl._llm_context()["context"] and "PENDING" in gl._llm_context()["context"]
    service.approve(pid)
    assert "get_trade_status" in gl._llm_context()["context"]


def test_slash_command_flow():
    pid = propose()["proposal_id"]
    assert pid in service.slash("")
    assert "solana:" in service.slash("approve")
    assert "Rejected" in service.slash("reject " + propose()["proposal_id"])
    assert "approved" in service.slash("receipts")
    assert "not found" not in service.slash("nonsense").lower()


def test_register_matches_manifest():
    from pathlib import Path

    import yaml

    manifest = yaml.safe_load((Path(gl.__file__).parent / "plugin.yaml").read_text())

    class Ctx:
        def __init__(self):
            self.tools, self.hooks, self.cmds, self.skills = [], [], [], []

        def get_config(self, key, default=None):
            return default

        def register_tool(self, name, **kw):
            assert callable(kw["handler"]) and kw["schema"]["name"] == name
            self.tools.append(name)

        def register_hook(self, name, fn):
            self.hooks.append(name)

        def register_command(self, name, **kw):
            self.cmds.append(name)

        def register_skill(self, name, path):
            self.skills.append(name)

    ctx = Ctx()
    gl.register(ctx)
    assert sorted(ctx.tools) == sorted(manifest["provides_tools"])
    assert sorted(ctx.hooks) == sorted(manifest["provides_hooks"])
    assert ctx.cmds == ["greenlight"] and ctx.skills == ["greenlight"]
