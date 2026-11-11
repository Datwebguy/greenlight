"""Backend routes for the Greenlight Desktop pane (mounted at /api/plugins/greenlight/)."""

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

_PKG = "greenlight_plugin_pkg"


def _core():
    if _PKG not in sys.modules:
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(_PKG, root / "__init__.py", submodule_search_locations=[str(root)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_PKG] = mod
        spec.loader.exec_module(mod)
    return sys.modules[_PKG]


def _call(fn, *args):
    core = _core()
    service, bridge = core.service, core.bridge
    try:
        return fn(service, *args)
    except service.GreenlightError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except bridge.BridgeError as e:
        raise HTTPException(status_code=502, detail=e.message)


def _changed(pid):
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event

        broadcast_plugin_event("greenlight", "proposal.updated", {"id": pid})
    except Exception:
        pass


router = APIRouter()


@router.get("/pending")
async def pending():
    return _call(lambda s: s.pending())


@router.post("/proposals/{proposal_id}/approve")
async def approve(proposal_id: str):
    out = _call(lambda s, i: s.approve(i), proposal_id)
    _changed(proposal_id)
    return out


@router.post("/proposals/{proposal_id}/reject")
async def reject(proposal_id: str):
    out = _call(lambda s, i: s.reject(i), proposal_id)
    _changed(proposal_id)
    return out


@router.post("/proposals/{proposal_id}/done")
async def done(proposal_id: str):
    out = _call(lambda s, i: s.dismiss(i), proposal_id)
    _changed(proposal_id)
    return out


@router.post("/demo")
async def demo():
    out = _call(lambda s: s.demo_proposal())
    _changed(out.get("proposal_id"))
    return out


@router.get("/receipts")
async def receipts(limit: int = 10):
    return _call(lambda s, n: s.list_receipts(n), limit)
