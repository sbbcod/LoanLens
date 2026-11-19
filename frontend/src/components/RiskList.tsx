import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { useState } from 'react'
import { api } from '../api/client'
import type { Risk } from '../api/types'
import { SEVERITY_DOT } from '../lib/severity'

const SOURCE_LABEL: Record<Risk['source'], string> = {
  rule: 'Policy rule',
  llm: 'AI review',
  system: 'Evidence check',
}

/** "§4.2" -> the clause text, from the policy document the backend serves. */
function useClause(ref: string | null): string | null {
  const { data } = useQuery({ queryKey: ['policy'], queryFn: api.policy, staleTime: Infinity })
  if (!ref || !data) return null
  const line = data.split('\n').find((l) => l.startsWith(`${ref} `))
  return line ? line.slice(ref.length).replace(/\*\*\[System check\]\*\*/, '').trim() : null
}

function RiskRow({ risk, canEdit, onToggle, busy }: {
  risk: Risk
  canEdit: boolean
  onToggle: (r: Risk) => void
  busy: boolean
}) {
  const [showClause, setShowClause] = useState(false)
  const clause = useClause(showClause ? risk.policy_ref : null)

  return (
    <li className={clsx('px-4 py-3.5', risk.acknowledged && 'opacity-55')}>
      <div className="flex gap-3">
        <span className={clsx('mt-1.5 size-2 shrink-0 rounded-full', SEVERITY_DOT[risk.severity])} />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-stone-800">{risk.message}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-500">
            <span className={clsx(risk.severity === 'critical' && 'font-medium text-red-700')}>
              {risk.severity === 'critical' ? 'Critical' : risk.severity === 'warning' ? 'Warning' : 'Note'}
            </span>
            <span>{SOURCE_LABEL[risk.source]}</span>
            {risk.policy_ref && (
              <button onClick={() => setShowClause((s) => !s)} className="text-ink-600 hover:underline">
                Policy {risk.policy_ref}
              </button>
            )}
            {risk.acknowledged && risk.acknowledged_by && (
              <span>Acknowledged by {risk.acknowledged_by.replace('user:', '')}</span>
            )}
          </div>
          {showClause && clause && (
            <p className="mt-2 rounded-lg bg-stone-50 px-3 py-2 text-xs leading-relaxed text-stone-600">{clause}</p>
          )}
        </div>
        {canEdit && (
          <label className="flex shrink-0 cursor-pointer items-start gap-2 pt-0.5 text-xs text-stone-500">
            <input type="checkbox" checked={risk.acknowledged} disabled={busy}
                   onChange={() => onToggle(risk)} className="mt-px size-3.5 accent-ink-700" />
            Seen
          </label>
        )}
      </div>
    </li>
  )
}

export function RiskList({ risks, canEdit, onToggle, busy }: {
  risks: Risk[]
  canEdit: boolean
  onToggle: (r: Risk) => void
  busy: boolean
}) {
  if (!risks.length) {
    return <p className="px-4 py-6 text-sm text-stone-500">No policy issues found.</p>
  }
  return (
    <ul className="divide-y divide-stone-100">
      {risks.map((r) => <RiskRow key={r.id} risk={r} canEdit={canEdit} onToggle={onToggle} busy={busy} />)}
    </ul>
  )
}
