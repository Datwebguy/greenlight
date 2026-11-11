// Greenlight approval pane (Hermes Desktop Plugin SDK).
// Shows pending xStocks proposals with quote, risk and daily cap, and lets the
// user Approve or Reject. The unsigned transaction / Solana Pay link is only
// shown after approval. This pane never signs or broadcasts anything.
import { Badge, Button, CopyButton, STATUSBAR_AREAS, host, haptic } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const el = (tag, props, ...children) => jsxs(tag, { ...props, children })
const muted = 'text-(--ui-text-tertiary)'
const short = (w) => (w && w.length > 12 ? `${w.slice(0, 4)}…${w.slice(-4)}` : w || '')
const usd = (n) => `$${Number(n).toFixed(2)}`
const capText = (c) => (c.limit_usd == null ? `no cap set (${usd(c.used_usd)} today)` : `${usd(c.used_usd)} / ${usd(c.limit_usd)}`)

function Row({ label, value }) {
  return el('div', { className: 'flex justify-between gap-3 text-xs' },
    jsx('span', { className: muted, children: label }),
    jsx('span', { className: 'text-right font-mono', children: value }))
}

function RiskBar({ risk }) {
  return el('div', { className: 'flex flex-col gap-1' },
    el('div', { className: 'flex items-center justify-between text-xs' },
      jsx('span', { className: muted, children: 'Risk score' }),
      jsx(Badge, { children: `${risk.score}/100 · ${risk.level}` })),
    jsx('div', {
      className: 'h-1.5 w-full overflow-hidden rounded-full border border-(--ui-stroke-secondary)',
      children: jsx('div', { className: 'h-full bg-(--ui-accent)', style: { width: `${risk.score}%` } })
    }),
    ...risk.factors.map(f =>
      jsx('div', { key: f.name, className: `text-[0.6875rem] ${muted}`, children: `+${f.points} ${f.name}: ${f.note}` })))
}

function Proposal({ p, busy, onApprove, onReject }) {
  const q = p.quote || {}
  return el('div', { className: 'flex flex-col gap-2 rounded-md border border-(--ui-stroke-secondary) p-3' },
    el('div', { className: 'flex items-center justify-between' },
      jsx('span', { className: 'text-sm font-medium', children: `${p.side.toUpperCase()} ${p.asset}` }),
      jsx('span', { className: `text-[0.6875rem] ${muted}`, children: `${p.seconds_left}s left` })),
    jsx(Row, { label: 'You pay', value: q.amountIn }),
    jsx(Row, { label: 'You receive (est.)', value: q.expectedOut }),
    jsx(Row, { label: 'Fee', value: q.fee }),
    p.implied_price_usd && jsx(Row, { label: 'Price (est.)', value: `${usd(p.implied_price_usd)} / share` }),
    jsx(Row, { label: 'Slippage', value: `${q.slippageBps} bps` }),
    jsx(Row, { label: 'Trade value', value: p.unpriced ? 'not priced in USD' : usd(p.notional_usd) }),
    jsx(Row, { label: 'Wallet', value: short(p.wallet) }),
    jsx(RiskBar, { risk: p.risk }),
    p.cap.limit_usd != null && jsx(Row, { label: 'Daily cap remaining after', value: `${usd(p.cap.remaining_after_usd)} of ${usd(p.cap.limit_usd)}` }),
    el('div', { className: 'flex gap-2 pt-1' },
      jsx(Button, { disabled: busy, onClick: () => onApprove(p.id), children: 'Approve' }),
      jsx(Button, { variant: 'outline', disabled: busy, onClick: () => onReject(p.id), children: 'Reject' })),
    jsx('div', { className: `text-[0.6875rem] ${muted}`, children: `Proposal ${p.id}. Approving releases an unsigned transaction only; Greenlight never signs.` }))
}

function Released({ p, ctx }) {
  return el('div', { className: 'flex flex-col gap-2 rounded-md border border-(--ui-accent) p-3' },
    jsx('span', { className: 'text-sm font-medium', children: `Approved: ${p.side} ${p.asset}` }),
    p.solanaPayUrl
      ? el('div', { className: 'flex gap-2' },
          jsx(Button, { onClick: () => ctx.os.openExternal(p.solanaPayUrl), children: 'Open in wallet' }),
          jsx(CopyButton, { text: p.solanaPayUrl }))
      : jsx('div', { className: `text-xs ${muted}`, children: 'No Solana Pay link; ask the agent for the unsigned transaction.' }),
    jsx('div', { className: `text-[0.6875rem] ${muted}`, children: 'Your wallet signs and sends. Ask the agent to check status with get_trade_status.' }))
}

function Receipts({ ctx }) {
  const [rc, setRc] = useState(null)
  useEffect(() => {
    const load = () => ctx.rest('/receipts?limit=5').then(setRc).catch(() => {})
    load()
    return ctx.setInterval(load, 5000)
  }, [ctx])
  if (!rc || rc.receipts.length === 0) return null
  return el('div', { className: 'flex flex-col gap-1 border-t border-(--ui-stroke-secondary) pt-2' },
    el('div', { className: 'flex items-center justify-between text-xs' },
      jsx('span', { className: muted, children: 'Recent receipts' }),
      jsx('span', { className: muted, children: rc.chain_ok ? 'chain verified' : 'CHAIN BROKEN' })),
    ...rc.receipts.map(r => jsx('div', {
      key: r.id, className: 'font-mono text-[0.6875rem]',
      children: `${r.ts.slice(11, 19)} ${r.event} ${r.proposal_id}${r.data && r.data.notional_usd != null ? ' ' + usd(r.data.notional_usd) : ''}`
    })))
}

function Pane({ ctx }) {
  const [data, setData] = useState({ pending: [], approved: [], cap: null })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(() => {
    ctx.rest('/pending').then(setData).catch(e => setError(String(e && e.message || e)))
  }, [ctx])

  useEffect(() => {
    refresh()
    const stopEvents = [ctx.onEvent('plugin.greenlight.proposal.created', refresh),
                        ctx.onEvent('plugin.greenlight.proposal.updated', refresh)]
    const timer = ctx.setInterval(refresh, 3000) // polling fallback
    return () => { stopEvents.forEach(s => s()); timer() }
  }, [ctx, refresh])

  const act = (verb) => async (id) => {
    setBusy(true); setError(''); haptic('tap')
    try {
      await ctx.rest(`/proposals/${id}/${verb}`, { method: 'POST', body: {} })
      host.notify({ kind: 'info', message: verb === 'approve' ? 'Greenlight: approved' : 'Greenlight: rejected' })
    } catch (e) {
      const d = e && e.detail && e.detail.message
      setError(d || String(e && e.message || e))
    } finally { setBusy(false); refresh() }
  }

  const cap = data.cap
  return el('div', { className: 'flex h-full flex-col gap-3 overflow-auto p-3 text-sm' },
    el('div', { className: 'flex items-center justify-between' },
      jsx('span', { className: 'font-medium', children: 'Greenlight' }),
      cap && jsx('span', { className: `text-xs ${muted}`, children: `Daily cap: ${capText(cap)}` })),
    error && jsx('div', { className: 'text-xs text-(--ui-accent)', children: error }),
    data.pending.length === 0 && data.approved.length === 0 &&
      jsx('div', { className: muted, children: 'No trades waiting. Ask Hermes: "Propose buying $25 of NVDAx".' }),
    ...data.pending.map(p => jsx(Proposal, { key: p.id, p, busy, onApprove: act('approve'), onReject: act('reject') })),
    ...data.approved.map(p => jsx(Released, { key: p.id, p, ctx })),
    jsx(Receipts, { ctx }))
}

function Chip({ ctx }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    const load = () => ctx.rest('/pending').then(d => setN(d.pending.length)).catch(() => {})
    load()
    const off = [ctx.onEvent('plugin.greenlight.proposal.created', load), ctx.onEvent('plugin.greenlight.proposal.updated', load)]
    const t = ctx.setInterval(load, 4000)
    return () => { off.forEach(f => f()); t() }
  }, [ctx])
  return jsx('button', {
    type: 'button',
    className: `px-1.5 text-[0.6875rem] ${n ? 'font-medium text-(--ui-accent)' : muted}`,
    onClick: () => { haptic('tap'); openApproval(ctx) },
    children: n ? `Greenlight · ${n} awaiting approval` : 'Greenlight'
  })
}

function openApproval(ctx) {
  try { host.openWorkspace('greenlight', { title: 'Greenlight', render: () => jsx(Pane, { ctx }) }) } catch (e) { /* the right-hand pane still works */ }
}

export default {
  id: 'greenlight',
  name: 'Greenlight',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'greenlight',
      data: { placement: 'right', width: '340px' },
      render: () => jsx(Pane, { ctx })
    })
    ctx.register({ id: 'chip', area: STATUSBAR_AREAS.right, order: 120, render: () => jsx(Chip, { ctx }) })
    ctx.onEvent('plugin.greenlight.proposal.created', () => {
      host.notify({ kind: 'info', title: 'Greenlight', message: 'A trade is waiting for your approval.' })
      ctx.os.notify({ title: 'Greenlight', body: 'A trade is waiting for your approval.' })
      openApproval(ctx)
    })
  }
}
