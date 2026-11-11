import json

import pytest

import greenlight as gl
from greenlight import bridge, service, state, tools

REAL_CALL = bridge.call  # the shared fixture swaps bridge.call for a fake; some tests need the real one
WALLET = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"


class FakeSdk:
    def __init__(self):
        self.expected = "0.470123 NVDAx"
        self.calls = 0

    def call(self, op, payload=None, timeout=45):
        if op == "assets":
            return {"assets": [{"symbol": "NVDAx", "mint": "Xs" + "a" * 40}],
                    "payTokens": [{"symbol": "USDC"}, {"symbol": "SOL"}]}
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
    monkeypatch.setenv("GREENLIGHT_DAILY_CAP_USD", "250")  # limits are opt-in; most tests turn the cap on
    monkeypatch.setenv("GREENLIGHT_MAX_TRADE_USD", "0")
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


def test_sol_needs_max_usd_only_when_a_limit_is_set():
    out = propose(pay_token="SOL")  # cap is on in this fixture
    assert out["error"] == "max_usd_required"
    assert propose(pay_token="SOL", max_usd=40)["notional_usd"] == 40


def test_no_limits_by_default(monkeypatch):
    monkeypatch.delenv("GREENLIGHT_DAILY_CAP_USD")
    monkeypatch.delenv("GREENLIGHT_MAX_TRADE_USD")
    big = propose(amount=100000)
    assert big["status"] == "pending_approval" and big["cap"]["limit_usd"] is None
    assert "No daily limit" in big["summary"]
    odd = propose(amount=12.34, pay_token="SOL")  # unpriced SOL leg is fine with no limits
    assert odd["status"] == "pending_approval" and odd["notional_usd"] is None
    assert propose(amount=0.01)["status"] == "pending_approval"
    assert "No daily limit" in service.slash("")
    assert service.approve(big["proposal_id"])["status"] == "approved"


def test_pay_token_comes_from_live_api():
    assert propose(pay_token="DOGE")["error"] == "invalid_pay_token"
    assert propose(pay_token="usdc")["status"] == "pending_approval"


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
    assert "approved" in service.slash("history").lower()
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


def test_demo_flow_releases_nothing_and_skips_limits(monkeypatch):
    monkeypatch.setenv("GREENLIGHT_MAX_TRADE_USD", "1")  # would reject $25 if limits applied
    d = service.demo_proposal()
    assert d["status"] == "pending_approval" and d["cap"]["used_usd"] == 0
    assert json.loads(tools.get_trade_status({"proposal_id": d["proposal_id"]}))["demo"] is True
    approved = service.approve(d["proposal_id"])
    assert approved["status"] == "approved" and "solanaPayUrl" not in approved and "transaction" not in approved
    assert "nothing is ever released" in approved["note"]
    assert "nothing is ever released" in json.dumps(json.loads(tools.get_trade_status({"proposal_id": d["proposal_id"]})))
    assert service.pending()["cap"]["used_usd"] == 0
    assert "Practice trade" in service.slash("demo")


def test_vendored_sdk_loads_without_network_or_npm():
    import subprocess
    from pathlib import Path

    root = Path(gl.__file__).parent
    out = subprocess.run(["node", str(root / "sdk-bridge.js")], input='{"op":"nope"}', capture_output=True, text=True)
    assert json.loads(out.stdout)["error"]["code"] == "bad_op"  # reached the op switch, so the SDK loaded
    assert not (root / "node_modules").exists()


# ---------------------------------------------------------------- audit coverage

def test_inputs_are_forgiving(monkeypatch):
    monkeypatch.delenv("GREENLIGHT_DAILY_CAP_USD")
    out = json.loads(tools.propose_trade({"asset": "$nvdax", "amount": "$1,250.50", "side": " Buy ", "wallet": WALLET,
                                          "pay_token": "usdc"}))
    assert out["status"] == "pending_approval" and out["quote"]["amountIn"].startswith("1250.5")
    assert propose(asset="NVDA")["status"] == "pending_approval"  # trailing x is optional
    assert propose(amount=True)["error"] == "invalid_amount"
    assert propose(amount="abc")["error"] == "invalid_amount"


def test_bare_strips_only_one_x():
    assert service._bare("BOXx") == "box" and service._bare("NVDAx") == "nvda" and service._bare("XOM") == "xom"


def test_approval_does_not_hold_the_state_lock(env, monkeypatch):
    import threading
    import time as _t

    pid = propose()["proposal_id"]
    gate, entered = threading.Event(), threading.Event()
    real = env.call

    def slow(op, payload=None, timeout=45):
        if op == "buildOrder":
            entered.set()
            gate.wait(5)
        return real(op, payload, timeout)

    monkeypatch.setattr(bridge, "call", slow)
    t = threading.Thread(target=service.approve, args=(pid,))
    t.start()
    assert entered.wait(5)
    started = _t.time()
    service.pending()  # the pane polls while the network call is in flight
    assert _t.time() - started < 1.0
    gate.set()
    t.join(5)
    assert json.loads(tools.get_trade_status({"proposal_id": pid}))["status"] == "approved"


def test_reject_during_approval_wins(env, monkeypatch):
    import threading

    pid = propose()["proposal_id"]
    entered, gate = threading.Event(), threading.Event()
    real = env.call

    def slow(op, payload=None, timeout=45):
        if op == "buildOrder":
            entered.set()
            gate.wait(5)
        return real(op, payload, timeout)

    monkeypatch.setattr(bridge, "call", slow)
    box = {}

    def run():
        try:
            service.approve(pid)
        except service.GreenlightError as e:
            box["err"] = e.code

    t = threading.Thread(target=run)
    t.start()
    entered.wait(5)
    service.reject(pid)
    gate.set()
    t.join(5)
    assert box["err"] == "not_pending"
    out = json.loads(tools.get_trade_status({"proposal_id": pid}))
    assert out["status"] == "rejected" and "solanaPayUrl" not in out


def test_release_window_and_done(monkeypatch):
    pid = propose()["proposal_id"]
    url = service.approve(pid)["solanaPayUrl"]
    assert service.pending()["approved"][0]["id"] == pid and gl._gate("browser", {"u": url}) is None
    service.dismiss(pid)
    assert service.pending()["approved"] == []
    assert gl._gate("browser", {"u": url})["action"] == "block"  # no longer an active release
    assert gl._llm_context() is None

    pid2 = propose()["proposal_id"]
    service.approve(pid2)
    monkeypatch.setenv("GREENLIGHT_RELEASE_WINDOW_MINUTES", "0.0001")
    import time as _t
    _t.sleep(0.05)
    out = json.loads(tools.get_trade_status({"proposal_id": pid2}))
    assert "solanaPayUrl" not in out and "window has ended" in out["note"]
    assert service.pending()["approved"] == []


def test_corrupt_state_is_set_aside_not_overwritten(tmp_path):
    (tmp_path / "state.json").write_text("{not json")
    propose()
    assert list(tmp_path.glob("state.corrupt-*.json"))
    assert json.loads((tmp_path / "state.json").read_text())["proposals"]


def test_old_finished_proposals_are_pruned_but_receipts_kept(tmp_path):
    pid = propose()["proposal_id"]
    service.reject(pid)
    p = tmp_path / "state.json"
    s = json.loads(p.read_text())
    s["proposals"][pid]["created_at_ts"] -= (state.RETENTION_DAYS + 1) * 86400
    p.write_text(json.dumps(s))
    service.pending()
    s = json.loads(p.read_text())
    assert pid not in s["proposals"] and s["receipts"] and state.verify_chain(s["receipts"])


def test_done_route_and_error_text(env, monkeypatch):
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    root = Path(gl.__file__).parent
    spec = importlib.util.spec_from_file_location("gl_plugin_api2", root / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    monkeypatch.setattr(api._core().bridge, "call", env.call)
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    pid = propose()["proposal_id"]
    c.post("/proposals/%s/approve" % pid)
    assert c.post("/proposals/%s/done" % pid).status_code == 200
    assert c.get("/pending").json()["approved"] == []
    bad = c.post("/proposals/%s/approve" % pid)
    assert bad.status_code == 409 and isinstance(bad.json()["detail"], str)


# ------------------------------------------------- no Node.js needed, retry, stale list

class _Resp:
    def __init__(self, body, status=200):
        self.status, self._b = status, json.dumps(body).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_works_without_node(monkeypatch):
    monkeypatch.setattr(bridge, "call", REAL_CALL)
    import urllib.error
    import urllib.request

    seen = []

    def fake_urlopen(req, timeout=30):
        seen.append((req.get_method(), req.full_url, req.data))
        if req.full_url.endswith("assets.json"):
            return _Resp({"assets": [{"symbol": "NVDAx", "mint": "m"}], "payTokens": [{"symbol": "USDC"}]})
        if req.full_url.endswith("/agent/build-order"):
            return _Resp({"status": "ready", "transaction": "T", "details": {"expectedOut": "1 NVDAx"}})
        return _Resp({"status": "confirmed", "signature": "S", "tx": ""})

    monkeypatch.setattr(bridge, "_node_path", {"checked": True, "path": None})  # pretend Node.js is not installed
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert bridge.get_assets()["assets"][0]["symbol"] == "NVDAx"
    assert bridge.build_order(WALLET, "NVDAx", 25, "buy", "USDC")["status"] == "ready"
    assert bridge.order_status("S")["status"] == "confirmed"
    methods = [(m, u.split("xstocker.com")[1]) for m, u, d in seen]
    assert methods == [("GET", "/agent/assets.json"), ("POST", "/agent/build-order"), ("GET", "/agent/order/S")]
    body = json.loads(seen[1][2])
    assert body == {"wallet": WALLET, "asset": "NVDAx", "amount": 25, "pay_token": "USDC", "side": "buy"}


def test_direct_path_errors_are_plain(monkeypatch):
    monkeypatch.setattr(bridge, "call", REAL_CALL)
    import urllib.error
    import urllib.request

    monkeypatch.setattr(bridge, "_node_path", {"checked": True, "path": None})
    monkeypatch.setattr(bridge, "RETRY_WAIT", 0)

    def busy(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 429, "x", {}, __import__("io").BytesIO(b'{"message":"slow down"}'))

    monkeypatch.setattr(urllib.request, "urlopen", busy)
    with pytest.raises(bridge.BridgeError) as e:
        bridge.get_assets()
    assert e.value.code == "busy" and "busy" in e.value.message

    def down(req, timeout=30):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    with pytest.raises(bridge.BridgeError) as e:
        bridge.get_assets()
    assert e.value.code == "unreachable" and "internet connection" in e.value.message


def test_busy_service_is_retried_once(monkeypatch):
    monkeypatch.setattr(bridge, "call", REAL_CALL)
    calls = {"n": 0}

    def flaky(op, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise bridge.BridgeError("busy", "busy")
        return {"ok": True}

    monkeypatch.setattr(bridge, "_node_path", {"checked": True, "path": None})
    monkeypatch.setattr(bridge, "_call_python", flaky)
    monkeypatch.setattr(bridge, "RETRY_WAIT", 0)
    assert bridge.call("assets") == {"ok": True} and calls["n"] == 2


def test_stale_stock_list_survives_a_blip(env, monkeypatch):
    assert propose()["status"] == "pending_approval"  # fills the cache
    service._assets_cache["ts"] = 0.0  # expired

    def blip(op, payload=None, timeout=45):
        if op == "assets":
            raise bridge.BridgeError("busy", "busy")
        return env.call(op, payload, timeout)

    monkeypatch.setattr(bridge, "call", blip)
    assert propose()["status"] == "pending_approval"


# ------------------------------------------------------------------ QR code for the wallet link

def _finder_ok(rows, x0, y0):
    ring = ["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"]
    return all(rows[y0 + dy][x0:x0 + 7] == ring[dy] for dy in range(7))


def test_qr_structure_and_sizes():
    from greenlight import qr

    for text in ("hi", "x" * 100, "solana:https%3A%2F%2Fxstocker.com%2Fagent%2Fpay%3Fasset%3DNVDAx" + "a" * 120):
        for ecl in ("L", "M"):
            rows = qr.encode(text, ecl)
            n = len(rows)
            assert (n - 17) % 4 == 0 and all(len(r) == n for r in rows)
            assert _finder_ok(rows, 0, 0) and _finder_ok(rows, n - 7, 0) and _finder_ok(rows, 0, n - 7)
    with pytest.raises(ValueError):
        qr.encode("x" * 5000)


def test_qr_round_trips_with_a_real_scanner():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from greenlight import qr

    det = cv2.QRCodeDetector()
    for text in ("hello", "solana:https%3A%2F%2Fxstocker.com%2Fagent%2Fpay%3Fasset%3DNVDAx%26amount%3D25%26side%3Dbuy" * 2):
        rows, scale, quiet = qr.encode(text, "M"), 8, 4
        n = len(rows)
        img = np.full(((n + 2 * quiet) * scale,) * 2, 255, np.uint8)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == "1":
                    img[(y + quiet) * scale:(y + quiet + 1) * scale, (x + quiet) * scale:(x + quiet + 1) * scale] = 0
        assert det.detectAndDecode(img)[0] == text


def test_qr_only_for_an_active_real_approval():
    from greenlight import qr

    pid = propose()["proposal_id"]
    with pytest.raises(service.GreenlightError):  # still pending: no link, so no code
        service.qr_for(pid)
    url = service.approve(pid)["solanaPayUrl"]
    out = service.qr_for(pid)
    assert out["rows"] == qr.encode(url, "M") and out["size"] == len(out["rows"])
    service.dismiss(pid)
    with pytest.raises(service.GreenlightError):  # done: link no longer active
        service.qr_for(pid)
    d = service.demo_proposal()["proposal_id"]
    service.approve(d)
    with pytest.raises(service.GreenlightError):  # practice trades never have a link
        service.qr_for(d)


def test_qr_route(env, monkeypatch):
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    root = Path(gl.__file__).parent
    spec = importlib.util.spec_from_file_location("gl_plugin_api3", root / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    monkeypatch.setattr(api._core().bridge, "call", env.call)
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    pid = propose()["proposal_id"]
    assert c.get("/proposals/%s/qr" % pid).status_code == 409
    c.post("/proposals/%s/approve" % pid)
    ok = c.get("/proposals/%s/qr" % pid)
    assert ok.status_code == 200 and ok.json()["rows"] and set("".join(ok.json()["rows"])) <= {"0", "1"}
