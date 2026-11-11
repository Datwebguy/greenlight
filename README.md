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
