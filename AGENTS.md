# Agent Instructions

You are building the Greenlight Hermes Agent plugin.

## First step
Read every markdown file in this repository before writing any code:
- README.md
- PRODUCT.md
- PROJECT.md
- RESOURCES.md
- ARCHITECTURE.md
- TOOLS.md
- DESKTOP_PANE.md
- CATALOG_SUBMISSION.md
- skills/greenlight/SKILL.md
- DEMO.md
- SUBMISSION.md

## Hard rules
- Do not list Claude, Anthropic, or any Claude model as author or co-author in commits, README, plugin.yaml, catalog entry, or any other file.
- Build the complete plugin. Do not leave stubs that prevent the full flow from working.
- The plugin must be non-custodial. It never holds or uses private keys.
- Always return JSON strings from tool handlers. Never raise exceptions out of a handler.
- Prefer the surfaces already defined (tools, hooks, Desktop pane, skill).

## Build order
1. Local state + propose_trade handler with simulation
2. Node bridge to @xstocker/agent-sdk
3. Desktop approval pane
4. Daily caps, receipts, and approval gating
5. Bundled skill
6. Validation with `hermes plugins validate`
7. README polish and catalog-ready structure

## Success criteria
- User can say “propose buying $25 of NVDAx”
- Plugin returns a proposal with quote and risk
- Desktop pane shows the proposal with Approve / Reject
- Approval releases the unsigned transaction or solanaPayUrl
- A local receipt is written
- Plugin passes `hermes plugins validate`
