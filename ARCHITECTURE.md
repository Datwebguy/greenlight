# Architecture

## Components
1. **Python plugin** (`__init__.py`, `tools.py`, `state.py`)
   - Registers tools and hooks
   - Owns local state (caps, proposals, receipts)
   - Calls Node bridge for the agent SDK

2. **Node bridge** (`sdk-bridge.js`)
   - Thin wrapper around `@xstocker/agent-sdk`
   - Receives args, returns JSON of unsigned order

3. **Desktop pane** (`desktop/plugin.js`)
   - Native Hermes Desktop surface
   - Shows pending proposal, risk, quote
   - Approve / Reject buttons that update local state

4. **Bundled skill** (`skills/greenlight/SKILL.md`)
   - Instructs Hermes to always propose first and surface the pane

## Data flow
User intent → `propose_trade` tool → agent-sdk quote + unsigned tx → local proposal stored → Desktop pane displays → user approves → unsigned material released → receipt written.

## Safety invariants
- No private keys ever enter the plugin.
- No unsigned transaction is returned until approval.
- Daily cap is checked before proposal is created.
- All state is local.
