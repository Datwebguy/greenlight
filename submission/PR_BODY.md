## What does this PR do?
Adds Greenlight to the plugin catalog (Plugin Hackathon entry). Greenlight gives xStocks trades on Solana an explicit approval step inside Hermes. `propose_trade` simulates an order against the live xStocks API through the official `@xstocker/agent-sdk` and returns a quote, a 0-100 risk score with its factors and the remaining daily cap, but never a transaction. The user approves or rejects in a native Desktop approval pane (or with `/greenlight` in the terminal and messaging chats); only then does `get_trade_status` release an unsigned transaction or Solana Pay link, rebuilt fresh and refused if the quote drifted. Non-custodial: it never holds, reads or signs with a private key and never broadcasts.

It is a standalone plugin published from its own repository, as CONTRIBUTING.md directs for third-party product integrations: https://github.com/Datwebguy/greenlight (pinned at `dce8cb8cc813dd912bba4a7413eb7d8d200af5a1`).

## Related Issue
N/A (Plugin Hackathon entry)

## Type of Change
- [ ] Bug fix
- [x] New feature (a new catalog entry; adds one file, changes nothing else)
- [ ] Security fix
- [ ] Documentation update
- [ ] Tests
- [ ] Refactor
- [ ] New skill (bundled or hub)

## Changes Made
- Adds `plugin-catalog/greenlight.yaml`, pinned to a full 40-character SHA, with `capabilities` matching what the plugin registers.

**Hermes surfaces used:** tools (`propose_trade`, `get_trade_status`, `list_receipts`), hooks (`pre_tool_call` approval gate, `pre_llm_call` pending-proposal reminder), a `/greenlight` slash command, the Desktop Plugin SDK (approval pane, status-bar chip, notifications), a bundled skill, `config_schema` settings and a pane backend (`dashboard/plugin_api.py`).

**Disclosure**
- Network: calls `api.xstocker.com` and `xstocker.com` through the official SDK. No other third-party services, no telemetry.
- Code: the SDK is vendored unmodified in `vendor/agent-sdk` (npm tarball sha1 and integrity in `VENDORED.md`). Nothing is installed or downloaded at runtime and the plugin never updates itself.
- Processes: a short-lived `node` process per SDK call with a fixed command line (`node sdk-bridge.js`, JSON on stdin). No shell, and never a model-chosen command.
- Files: writes proposals and receipts only to `<HERMES_HOME>/plugin-data/greenlight/`. Reads no credentials and holds no keys.
- No Python dependencies. Needs Node.js 18+.

## How to Test
1. `python3 scripts/validate_plugin_catalog.py plugin-catalog/greenlight.yaml` passes.
2. `hermes plugins install https://github.com/Datwebguy/greenlight && hermes plugins enable greenlight`.
3. `hermes plugins validate <checkout> --install-deps` and `hermes plugins doctor <checkout> --ci` pass (checked on v0.23.1).
4. Run `/greenlight demo` for a no-wallet walkthrough: live quote, risk score, approval pane, approve or reject, receipt.
5. In the plugin repo, `python -m pytest tests` runs 29 tests (approval gating, limits, receipts and tamper detection, quote-drift refusal, concurrent approve/reject, release window, both hooks, slash command, pane backend, demo mode, vendored SDK).

## Checklist
### Code
- [x] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md) (catalog and third-party plugin sections) and the catalog submission guide
- [x] My commit messages follow Conventional Commits
- [x] I searched for existing PRs to make sure this isn't a duplicate
- [x] My PR contains only changes related to this feature (one catalog file)
- [ ] `just test` / `just check`: not applicable to a one-file catalog entry; I ran the catalog validator and `hermes plugins validate` instead
- [ ] Added tests: the plugin's own tests live in its repository (see How to Test)
- [x] I've tested on my platform: Linux

### Documentation & Housekeeping
- [x] N/A: no changes to docs, config keys, architecture or tool schemas in this repository
- [x] Cross-platform: the plugin is pure Python plus Node.js and uses no platform-specific calls; it has been exercised on Linux

### For New Skills
N/A. The `greenlight` skill ships inside the plugin, not as a bundled or hub skill.

## Screenshots / Logs
```
$ hermes plugins validate . --install-deps
✓ manifest  ✓ requires_hermes  ✓ config schema  ✓ loadable  ✓ capability probe
✓ declared tools / hooks / middleware match registrations
✓ built-in tool collisions  ✓ security scan — safe  ✓ no core override  ✓ desktop surface
Validation passed.

$ python3 scripts/validate_plugin_catalog.py plugin-catalog/greenlight.yaml
OK: 1 file(s) valid
```
Screenshots of the Desktop approval pane will be added in a comment.
