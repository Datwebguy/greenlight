"""Greenlight: explicit approval for xStocks trades inside Hermes Agent."""

import logging
from pathlib import Path

from . import schemas, service, state, tools

logger = logging.getLogger(__name__)


def _gate(tool_name, args, task_id=None, **kwargs):
    """pre_tool_call: veto other tools carrying unapproved xStocks order links."""
    try:
        message = service.gate_check(tool_name, args)
    except Exception:  # a broken gate must not take the agent down
        logger.exception("greenlight gate failed")
        return None
    return {"action": "block", "message": message} if message else None


def register(ctx):
    state.configure(lambda key, default=None: ctx.get_config(key, default))
    for schema, handler in (
        (schemas.PROPOSE_TRADE, tools.propose_trade),
        (schemas.GET_TRADE_STATUS, tools.get_trade_status),
        (schemas.LIST_RECEIPTS, tools.list_receipts),
    ):
        ctx.register_tool(name=schema["name"], toolset="greenlight", schema=schema, handler=handler)
    ctx.register_hook("pre_tool_call", _gate)

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)
