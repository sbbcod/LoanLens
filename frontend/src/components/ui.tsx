// Small building blocks shared by every page. Kept deliberately plain.

import { clsx } from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Status } from '../api/types'
import { STATUS_LABEL } from '../lib/format'

export function Button({
  variant = 'secondary',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  return (
    <button
      className={clsx(
        'inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-40',
        variant === 'primary' && 'bg-ink-700 text-white hover:bg-ink-900',
        variant === 'secondary' && 'border border-stone-200 bg-white text-stone-700 hover:bg-stone-50',
        variant === 'ghost' && 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
        className,
      )}
      {...props}
    />
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx('rounded-xl border border-stone-200/80 bg-white', className)}>{children}</div>
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[13px] font-semibold uppercase tracking-wide text-stone-500">{children}</h2>
      {aside}
    </div>
  )
}

const STATUS_STYLE: Record<Status, string> = {
  received: 'bg-stone-100 text-stone-600',
  needs_review: 'bg-amber-50 text-amber-800 ring-amber-200',
  extracted: 'bg-ink-50 text-ink-700 ring-ink-100',
  reviewed: 'bg-ink-50 text-ink-700 ring-ink-100',
  pending_approval: 'bg-violet-50 text-violet-700 ring-violet-200',
  approved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  declined: 'bg-stone-100 text-stone-600 ring-stone-200',
  error: 'bg-red-50 text-red-700 ring-red-200',
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ring-transparent',
        STATUS_STYLE[status],
      )}
    >
      {status === 'received' && <span className="size-1.5 animate-pulse rounded-full bg-stone-400" />}
      {STATUS_LABEL[status]}
    </span>
  )
}

/** Thin bar: green from 0.85, amber from 0.6, red below. */
export function ConfidenceBar({ value, width = 'w-16' }: { value: number | null; width?: string }) {
  if (value == null) return <span className="text-stone-400">—</span>
  const colour = value >= 0.85 ? 'bg-emerald-500' : value >= 0.6 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <span className="inline-flex items-center gap-2" title={`Confidence ${Math.round(value * 100)}%`}>
      <span className={clsx('h-1.5 overflow-hidden rounded-full bg-stone-100', width)}>
        <span className={clsx('block h-full rounded-full', colour)} style={{ width: `${value * 100}%` }} />
      </span>
      <span className="w-8 text-xs tabular-nums text-stone-500">{Math.round(value * 100)}%</span>
    </span>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card className="px-5 py-4">
      <div className="text-[13px] text-stone-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-stone-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-stone-400">{hint}</div>}
    </Card>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={clsx('inline-block size-4 animate-spin rounded-full border-2 border-stone-200 border-t-ink-600', className)}
    />
  )
}
