"""Tool handlers. Always return a JSON string and never raise."""

import json
import logging

from . import service
from .bridge import BridgeError

log = logging.getLogger(__name__)


def _run(fn, *a):
    try:
        return json.dumps(fn(*a), default=str)
    except service.GreenlightError as e:
        return json.dumps(dict(e.extra, status="error", error=e.code, message=e.message), default=str)
    except BridgeError as e:
        return json.dumps({"status": "error", "error": e.code, "message": e.message})
    except Exception as e:  # never raise out of a handler
        log.exception("greenlight handler failed")
        return json.dumps({"status": "error", "error": "internal_error", "message": str(e)})


def _args(args):
    return args if isinstance(args, dict) else {}


def propose_trade(args, **kwargs):
    return _run(service.propose_trade, _args(args))


def get_trade_status(args, **kwargs):
    return _run(service.get_trade_status, _args(args))


def list_receipts(args, **kwargs):
    a = _args(args)
    return _run(service.list_receipts, a.get("limit", 10), a.get("proposal_id"))
