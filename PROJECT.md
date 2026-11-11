# Project: Greenlight

## Name
Greenlight

## Type
Hermes Agent plugin (tools + hooks + Desktop pane + skill)

## Goal
Ship a complete, validated Hermes plugin that can be submitted to the plugin catalog and used by any Hermes user.

## Deliverables
- Public GitHub repository
- Working plugin that passes `hermes plugins validate`
- Desktop approval pane
- Demo video showing the full flow
- Catalog PR adding `plugin-catalog/greenlight.yaml` with full 40-character SHA
- Form submission with both links

## Build order
1. Python tools + local state + simulation
2. @xstocker/agent-sdk bridge
3. Desktop approval pane
4. Caps, receipts, skill, gating
5. Validation, README, demo, catalog PR

## Author note
Do not use Claude (or any Anthropic model) as author or co-author in commits, README, or catalog entry.
