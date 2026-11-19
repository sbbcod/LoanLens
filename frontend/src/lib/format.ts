import type { FieldKind, FieldValue, Status } from '../api/types'

const aud = new Intl.NumberFormat('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })

export const money = (v: number | null | undefined) => (v == null ? '—' : aud.format(v))

/** $4,950,000 -> $4.95m, for tight table cells. */
export function moneyShort(v: number | null | undefined) {
  if (v == null) return '—'
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2).replace(/\.?0+$/, '')}m`
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`
  return aud.format(v)
}

export const percent = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${v.toFixed(digits)}%`

export function date(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function dateTime(iso: string) {
  return new Date(iso).toLocaleString('en-AU', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  })
}

export function relative(iso: string) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return date(iso)
}

export const humanise = (s: string | null | undefined) =>
  s ? s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '—'

const OPTION_LABELS: Record<string, string> = {
  smsf: 'SMSF',
  residential_dev: 'Residential development',
  mixed_use: 'Mixed use',
  equity_release: 'Equity release',
}

export const optionLabel = (v: string) => OPTION_LABELS[v] ?? humanise(v)

export function fieldValue(kind: FieldKind, v: FieldValue, name?: string): string {
  if (v == null || v === '') return '—'
  if (name === 'abn' && /^\d{11}$/.test(String(v))) {
    const s = String(v)
    return `${s.slice(0, 2)} ${s.slice(2, 5)} ${s.slice(5, 8)} ${s.slice(8)}`
  }
  switch (kind) {
    case 'money':
      return money(Number(v))
    case 'percent':
      return percent(Number(v))
    case 'integer':
      return `${v} months`
    case 'date':
      return date(String(v))
    case 'enum':
      return optionLabel(String(v))
    default:
      return String(v)
  }
}

export const STATUS_LABEL: Record<Status, string> = {
  received: 'Processing',
  needs_review: 'Needs review',
  extracted: 'Ready',
  reviewed: 'Reviewed',
  pending_approval: 'Awaiting approval',
  approved: 'Approved',
  declined: 'Declined',
  error: 'Error',
}
