// Greenlight approval window for Hermes Desktop.
// Shows each waiting trade in plain language (price, fee, risk, daily limit) and lets you
// Approve or Reject. The wallet link appears only after you approve. Nothing here signs or sends.
import { Badge, Button, CopyButton, STATUSBAR_AREAS, host, haptic } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const el = (tag, props, ...children) => jsxs(tag, { ...props, children })
const muted = 'text-(--ui-text-tertiary)'
const short = (w) => (w && w.length > 12 ? `${w.slice(0, 4)}…${w.slice(-4)}` : w || '')
const usd = (n) => `$${Number(n).toFixed(2)}`
const capText = (c) => (c.limit_usd == null ? 'No daily limit set' : `Today's limit: ${usd(c.used_usd)} of ${usd(c.limit_usd)}`)
const cap1 = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : t)
const clock = (secs) => `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
const EVENT = { approved: 'Approved', rejected: 'Rejected', expired: 'Expired', settled: 'Confirmed' }

function Row({ label, value }) {
  return el('div', { className: 'flex justify-between gap-3 text-xs' },
    jsx('span', { className: muted, children: label }),
    jsx('span', { className: 'text-right font-mono', children: value }))
}

function RiskBar({ risk }) {
  return el('div', { className: 'flex flex-col gap-1' },
    el('div', { className: 'flex items-center justify-between text-xs' },
      jsx('span', { className: muted, children: 'Risk check' }),
      jsx(Badge, { children: `${cap1(risk.level)} risk · ${risk.score}/100` })),
    jsx('div', {
      className: 'h-1.5 w-full overflow-hidden rounded-full border border-(--ui-stroke-secondary)',
      children: jsx('div', { className: 'h-full bg-(--ui-accent)', style: { width: `${risk.score}%` } })
    }),
    ...risk.factors.map(f =>
      jsx('div', { key: f.name, className: `text-[0.6875rem] ${muted}`, children: `${f.label || f.name}: ${f.note}` })))
}

function Proposal({ p, busy, onApprove, onReject }) {
  const q = p.quote || {}
  return el('div', { className: 'flex flex-col gap-2 rounded-md border border-(--ui-stroke-secondary) p-3' },
    el('div', { className: 'flex items-center justify-between' },
      jsx('span', { className: 'text-sm font-medium', children: `${cap1(p.side)} ${p.asset}${p.demo ? '  (practice)' : ''}` }),
      jsx('span', { className: `text-[0.6875rem] ${muted}`, children: `Expires in ${clock(p.seconds_left)}` })),
    jsx(Row, { label: 'You pay', value: q.amountIn }),
    jsx(Row, { label: 'You get (estimate)', value: q.expectedOut }),
    jsx(Row, { label: 'Fee', value: q.fee }),
    p.implied_price_usd && jsx(Row, { label: 'Price (estimate)', value: `${usd(p.implied_price_usd)} per share` }),
    jsx(Row, { label: 'Price movement allowed', value: `${(q.slippageBps / 100).toFixed(2)}%` }),
    jsx(Row, { label: 'Trade value', value: p.unpriced ? 'not priced in USD' : usd(p.notional_usd) }),
    jsx(Row, { label: 'Wallet', value: short(p.wallet) }),
    jsx(RiskBar, { risk: p.risk }),
    p.cap.limit_usd != null && jsx(Row, { label: 'Left in today\'s limit after this', value: `${usd(p.cap.remaining_after_usd)} of ${usd(p.cap.limit_usd)}` }),
    el('div', { className: 'flex gap-2 pt-1' },
      jsx(Button, { disabled: busy, onClick: () => onApprove(p.id), children: 'Approve' }),
      jsx(Button, { variant: 'outline', disabled: busy, onClick: () => onReject(p.id), children: 'Reject' })),
    jsx('div', { className: `text-[0.6875rem] ${muted}`, children: 'Approving gives you a link to confirm this trade in your own wallet. Greenlight never has your keys or your funds.' }))
}

function QrCode({ rows }) {
  // Wallet apps need dark modules on a light background, so these two colours are fixed on purpose.
  const n = rows.length
  const q = 3
  let d = ''
  rows.forEach((r, y) => {
    let x = 0
    while (x < n) {
      if (r[x] === '1') {
        let e = x
        while (e < n && r[e] === '1') e++
        d += `M${x + q} ${y + q}h${e - x}v1h-${e - x}z`
        x = e
      } else x++
    }
  })
  const side = n + q * 2
  return jsxs('svg', {
    viewBox: `0 0 ${side} ${side}`, width: 150, height: 150, role: 'img', shapeRendering: 'crispEdges',
    'aria-label': 'QR code for the wallet link', style: { borderRadius: 8, flex: 'none' },
    children: [jsx('rect', { width: side, height: side, fill: '#ffffff' }), jsx('path', { d, fill: '#000000' })]
  })
}

function Released({ p, ctx, onDone }) {
  const [qrRows, setQrRows] = useState(null)
  useEffect(() => {
    if (p.demo || !p.solanaPayUrl) return
    ctx.rest(`/proposals/${p.id}/qr`).then(r => setQrRows(r.rows)).catch(() => {})
  }, [ctx, p.id, p.demo, p.solanaPayUrl])
  const done = jsx(Button, { variant: 'outline', onClick: () => onDone(p.id), children: 'All done' })
  if (p.demo) {
    return el('div', { className: 'flex flex-col gap-2 rounded-md border border-(--ui-stroke-secondary) p-3' },
      jsx('span', { className: 'text-sm font-medium', children: `Practice trade approved: ${p.side} ${p.asset}` }),
      jsx('div', { className: `text-[0.6875rem] ${muted}`, children: 'This was a rehearsal. Nothing was sent anywhere.' }),
      done)
  }
  return el('div', { className: 'flex flex-col gap-2 rounded-md border border-(--ui-accent) p-3' },
    jsx('span', { className: 'text-sm font-medium', children: `Approved: ${p.side} ${p.asset}` }),
    p.solanaPayUrl
      ? el('div', { className: 'flex gap-2' },
          jsx(Button, { onClick: () => ctx.os.openExternal(p.solanaPayUrl), children: 'Open in wallet' }),
          jsx(CopyButton, { text: p.solanaPayUrl }),
          done)
      : jsx('div', { className: `text-xs ${muted}`, children: 'No wallet link was available. Ask Hermes for the transaction instead.' }),
    qrRows && el('div', { className: 'flex items-center gap-3' },
      jsx(QrCode, { rows: qrRows }),
      jsx('div', { className: `text-xs ${muted}`, children: 'Or scan this with your phone\'s wallet to confirm the trade.' })),
    jsx('div', { className: `text-[0.6875rem] ${muted}`, children: 'Open the link in your wallet to confirm the trade. Greenlight never signs or sends anything for you.' }))
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
      jsx('span', { className: muted, children: 'Recent activity' }),
      jsx('span', { className: muted, children: rc.chain_ok ? 'History verified' : 'History check failed' })),
    ...rc.receipts.map(r => jsx('div', {
      key: r.id, className: 'font-mono text-[0.6875rem]',
      children: `${r.ts.slice(11, 19)} · ${EVENT[r.event] || r.event}${r.data && r.data.asset ? ` · ${cap1(r.data.side || '')} ${r.data.asset}` : ''}${r.data && r.data.notional_usd != null ? ' · ' + usd(r.data.notional_usd) : ''}`
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
      host.notify({ kind: 'info', message: verb === 'approve' ? 'Trade approved.' : 'Trade rejected. Nothing was sent.' })
    } catch (e) {
      setError(String((e && (e.detail || e.message)) || e))
    } finally { setBusy(false); refresh() }
  }

  const markDone = async (id) => {
    try { await ctx.rest(`/proposals/${id}/done`, { method: 'POST', body: {} }) } catch (e) { /* refresh below */ }
    refresh()
  }

  const runDemo = async () => {
    setBusy(true); setError('')
    try { await ctx.rest('/demo', { method: 'POST', body: {} }) } catch (e) {
      setError(String((e && (e.detail || e.message)) || e))
    } finally { setBusy(false); refresh() }
  }

  const cap = data.cap
  return el('div', { className: 'flex h-full flex-col gap-3 overflow-auto p-3 text-sm' },
    el('div', { className: 'flex items-center justify-between' },
      jsx('span', { className: 'font-medium', children: 'Greenlight' }),
      cap && jsx('span', { className: `text-xs ${muted}`, children: capText(cap) })),
    error && jsx('div', { className: 'text-xs text-(--ui-accent)', children: error }),
    data.pending.length === 0 && data.approved.length === 0 &&
      el('div', { className: 'flex flex-col gap-2' },
        jsx('div', { className: muted, children: 'No trades waiting. Ask Hermes, for example: "Buy $25 of NVDAx".' }),
        jsx(Button, { variant: 'outline', disabled: busy, onClick: runDemo, children: 'Try a practice trade (no wallet needed)' })),
    ...data.pending.map(p => jsx(Proposal, { key: p.id, p, busy, onApprove: act('approve'), onReject: act('reject') })),
    ...data.approved.map(p => jsx(Released, { key: p.id, p, ctx, onDone: markDone })),
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
    children: n ? `Greenlight · ${n} trade${n > 1 ? 's' : ''} awaiting approval` : 'Greenlight'
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
