import type { AuditEntry } from '../api/types'
import { dateTime, humanise } from '../lib/format'

function describe(e: AuditEntry): string {
  const d = e.detail ?? {}
  switch (e.action) {
    case 'received':
      return `Received by ${d.source === 'email' ? 'email' : 'upload'}`
    case 'ai_processed':
      return `Read by AI (${String(d.model)})${
        Array.isArray(d.flags) && d.flags.length ? ` · ${d.flags.length} flag${d.flags.length > 1 ? 's' : ''}` : ''}`
    case 'field_edited':
      return `Corrected ${humanise(String(d.field)).toLowerCase()}: ${String(d.from ?? '—')} → ${String(d.to ?? '—')}`
    case 'risk_acknowledged':
      return `Acknowledged ${String(d.code)}`
    case 'risk_unacknowledged':
      return `Un-acknowledged ${String(d.code)}`
    case 'submitted_for_approval':
      return 'Sent for approval'
    case 'approval_requested':
      return d.channel === 'simulated' ? 'Approval request simulated (Teams not connected)' : 'Approval card sent to Teams'
    case 'approval_approved':
      return `Approved by ${String(d.approver)}`
    case 'approval_declined':
      return `Declined by ${String(d.approver)}`
    case 'processing_failed':
      return `Processing failed: ${String(d.error)}`
    default:
      return humanise(e.action)
  }
}

function actor(a: string) {
  if (a.startsWith('user:')) return a.slice(5)
  return { ai: 'AI', system: 'System', flow: 'Power Automate' }[a] ?? a
}

export function Activity({ entries }: { entries: AuditEntry[] }) {
  return (
    <ol className="space-y-0 px-4 py-3">
      {[...entries].reverse().map((e, i, all) => (
        <li key={e.id} className="relative flex gap-3 pb-4 last:pb-1">
          {i < all.length - 1 && <span className="absolute left-[3px] top-3 h-full w-px bg-stone-200" />}
          <span className="relative mt-1.5 size-[7px] shrink-0 rounded-full bg-stone-300 ring-4 ring-white" />
          <div className="min-w-0 text-[13px]">
            <p className="text-stone-700">{describe(e)}</p>
            <p className="text-xs text-stone-400">{actor(e.actor)} · {dateTime(e.created_at)}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
