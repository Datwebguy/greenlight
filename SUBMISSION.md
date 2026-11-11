# Hackathon submission checklist

Source: Nous Research "Hermes Agent Plugin Hackathon" announcement, the Hermes catalog submission guide and the catalog README.

**Deadline: November 11, 2026, 5PM EST (UTC-5).** Confirm on the official announcement and entry form; the deadline above comes from the announcement as quoted by the community judge checklist.

## Required to enter
| # | Requirement | Status |
|---|---|---|
| 1 | Public GitHub repository | Repo exists; confirm it is public |
| 2 | Plugin loads and passes `hermes plugins validate . --install-deps` | Passed on Hermes v0.23.1 (all checks green); `hermes plugins doctor . --ci` also passes |
| 3 | Demo video, strictly under 90 seconds, shows the plugin working | Script in DEMO.md; you record it |
| 4 | Video posted on X, tagging @NousResearch | You post it |
| 5 | Catalog PR to NousResearch/hermes-agent adding `plugin-catalog/greenlight.yaml`, full 40-char SHA | Draft in `submission/greenlight.yaml` |
| 6 | Entry form with BOTH links (catalog PR link and the X video link) | You submit it |

An unmerged catalog PR does not block submitting the form; it only needs to be open.

## Judging (as reported)
Usefulness, reliability, polish, creativity. No official weights found.

## Catalog admission rules that matter here
- Rule 2: exact 40-character SHA pin. Rule 3: no self-updating code (none; the SDK is pinned to 1.4.0).
- Rule 6: declared capabilities match what registers (tools: 3, hooks: `pre_tool_call`, `pre_llm_call`).
- Rule 8: desktop plugin uses only the SDK surface (no eval, no other imports).
- Rule 9: no core overrides (public `register_*` APIs only).
- Rule 11: no credential reads. Rule 12: approvals respected; nothing waits unattended without timing out (proposals expire).
- Rule 13: disclose risky behaviour in the PR and README (below).
- Rule 14: `requires_hermes` is a SemVer floor (latest Hermes release found: v0.23.1).
- Rule 17: no binaries or bytecode committed.

## PR description (draft)
**What it does:** Greenlight turns an xStocks trade request into a simulated proposal with a risk score and remaining daily cap, shows it in a Hermes Desktop pane, and releases the unsigned transaction only after explicit approval. Non-custodial: it never holds, reads or uses a private key and never signs or broadcasts.

**Hermes surfaces used:** tools (`propose_trade`, `get_trade_status`, `list_receipts`), hooks (`pre_tool_call` approval gate, `pre_llm_call` reminder), slash command (`/greenlight`), Desktop Plugin SDK pane and status-bar chip, bundled skill, plugin settings (`config_schema`), pane backend (`dashboard/plugin_api.py`).

**Disclosure (rule 13):**
- Network calls to `api.xstocker.com` and `xstocker.com` through the official `@xstocker/agent-sdk`. No other third-party services. No telemetry.
- The official `@xstocker/agent-sdk` 1.4.0 is vendored unmodified (`vendor/agent-sdk`, integrity recorded in `VENDORED.md`). Nothing is installed or downloaded at runtime; no self-updating code.
- Spawns a short-lived `node` subprocess per SDK call with a fixed command line and JSON on stdin. It never runs a model-chosen command and never uses a shell.
- Writes only to `<HERMES_HOME>/plugin-data/greenlight/` (proposals, receipts). Reads no credentials.

**Testing evidence:** 29 automated tests (`python -m pytest tests`) covering approval gating, limits, receipts and tamper detection, quote-drift refusal, concurrent approve/reject, the release window, both hooks, the slash command, the pane backend, demo mode and the vendored SDK; plus a live run against the xStocks API (propose then approve a $25 NVDAx buy).

Add screenshots of the pane to the PR.

## PR format (learned from a merged hackathon PR, NousResearch/hermes-agent#151376)
- Title: `feat(plugin-catalog): add greenlight plugin (Plugin Hackathon entry)` (Conventional Commits).
- Touch exactly one file: `plugin-catalog/greenlight.yaml`.
- Checklist in the description: contributing guide read, searched for duplicate PRs, change limited to one catalog file, `hermes plugins validate` run, tested on your OS, docs provided.
- Reviewers blocked that PR until a CLI path that ran a model-chosen shell command was removed. Greenlight has no such path; say so in the description.
- If the catalog yaml sets a banner `image` or `screenshots`, pin them to the same commit (GitHub-hosted, HTTPS).
- A maintainer may handle the disclosure line and version floor as a merge chore; do not wait on that to submit the form.
