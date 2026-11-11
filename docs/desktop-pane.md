# Desktop Pane

Native Hermes Desktop pane registered via the Desktop Plugin SDK.

## Location
`desktop/plugin.js`

## What it shows
- Pending proposal details (asset, side, amount, quote)
- Risk score
- Daily cap remaining
- Approve / Reject buttons

## Behavior
- Approve updates local state so the unsigned transaction or solanaPayUrl can be released.
- Reject marks the proposal rejected and writes a receipt.

## SDK reference
https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md
