# Greenlight

Explicit approval for xStocks trades inside Hermes Agent.

Greenlight turns a trade request into a simulated proposal with risk score and remaining daily cap, surfaces it in a native Desktop pane, and only releases an unsigned transaction after the user gives the green light. It never holds keys.

## What it does
- Accepts natural-language trade intents
- Builds unsigned transactions via @xstocker/agent-sdk
- Runs mandatory simulation + risk scoring
- Enforces local daily USD caps
- Shows a native Hermes Desktop approval pane
- Stores verifiable local receipts
- Hands the user a solanaPayUrl or unsigned transaction only after approval

## Quick start
```bash
hermes plugins install <your-repo-or-catalog-name>
```

Then ask Hermes:
```
Propose buying $25 of NVDAx
```
Approve in the Desktop pane.

## Surfaces used
- **Tools:** `propose_trade`, `get_trade_status`, `list_receipts`
- **Hooks:** approval gating
- **Desktop Plugin SDK:** approval pane
- **Bundled skill:** `greenlight`

## Important
- Non-custodial. The plugin never signs or broadcasts.
- All real movement requires explicit approval.
- Do not list Claude (or any Anthropic model) as author or co-author of this plugin or its commits.

## Links
- Agent SDK: https://www.npmjs.com/package/@xstocker/agent-sdk
- xStocks docs: https://docs.xstocks.fi
- Hermes plugin guide: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md
- Desktop SDK: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md
- Catalog submission: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md
