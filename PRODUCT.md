# Product: Greenlight

## One-line
Explicit green-light approval for xStocks trades in Hermes Agent — simulate, score, approve, then release the unsigned transaction.

## Problem
Agents that can move money need hard, inspectable guardrails. Generic safety plugins exist, but nothing gives Hermes a clean path for tokenized-stock trades on Solana that stays non-custodial and requires explicit approval before any transaction material is released.

## Solution
Greenlight turns a trade request into a simulated proposal with risk score and remaining daily cap, surfaces it in a Hermes Desktop pane, and only releases an unsigned transaction after the user approves.

## Core user journey
1. User says “buy $50 of NVDAx”.
2. Hermes calls `propose_trade`.
3. Plugin returns quote + risk + proposal ID.
4. Desktop pane shows the details and Approve / Reject buttons.
5. User approves.
6. Unsigned transaction or solanaPayUrl is released.
7. Receipt is stored locally.

## Differentiation
- Domain-specific (xStocks) rather than generic safety.
- Native Desktop approval surface.
- Mandatory simulation before any transaction material is released.
- Local receipts and daily caps.
- Built on the official @xstocker/agent-sdk (unsigned only).

## Non-goals
- Custodial signing
- Automatic execution
- Multi-chain in v1
- Complex portfolio optimization
