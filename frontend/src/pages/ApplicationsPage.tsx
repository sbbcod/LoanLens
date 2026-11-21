import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Search, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { api } from '../api/client'
import type { ApplicationSummary, Status } from '../api/types'
import { SEVERITY_DOT } from '../lib/severity'
import type { LayoutContext } from '../components/Layout'
import { Button, Card, ConfidenceBar, Loading, Spinner, Stat, StatusBadge } from '../components/ui'
import { moneyShort, optionLabel, percent, relative } from '../lib/format'
import { useSession } from '../lib/session'

const TABS: { label: string; status?: Status }[] = [
  { label: 'All' },
  { label: 'Needs review', status: 'needs_review' },
  { label: 'Ready', status: 'extracted' },
  { label: 'Awaiting approval', status: 'pending_approval' },
  { label: 'Approved', status: 'approved' },
  { label: 'Declined', status: 'declined' },
]

function RiskDots({ app }: { app: ApplicationSummary }) {
  const { critical, warning } = app.open_risks
  if (!critical && !warning) return <span className="text-xs text-stone-400">None</span>
  return (
    <span className="flex items-center gap-3 text-xs tabular-nums text-stone-600">
      {critical > 0 && (
        <span className="flex items-center gap-1.5"><span className={clsx('size-2 rounded-full', SEVERITY_DOT.critical)} />{critical}</span>
      )}
      {warning > 0 && (
        <span className="flex items-center gap-1.5"><span className={clsx('size-2 rounded-full', SEVERITY_DOT.warning)} />{warning}</span>
      )}
    </span>
  )
}

function UploadButton() {
  const session = useSession()
  const { requestUnlock } = useOutletContext<LayoutContext>()
  const input = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const upload = useMutation({
    mutationFn: api.upload,
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: ['applications'] })
      navigate(`/applications/${r.id}`)
    },
  })

  return (
    <>
      <input ref={input} type="file" accept="application/pdf" className="hidden"
             onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = '' }} />
      <Button variant="primary" disabled={upload.isPending}
              onClick={() => (session ? input.current?.click() : requestUnlock())}>
        {upload.isPending ? <Spinner className="border-white/30 border-t-white" /> : <Upload className="size-4" />}
        Upload PDF
      </Button>
      {upload.isError && <p className="text-sm text-red-600">{upload.error.message}</p>}
    </>
  )
}

export function ApplicationsPage() {
  const [tab, setTab] = useState(0)
  const [q, setQ] = useState('')
  const navigate = useNavigate()
  const status = TABS[tab].status

  const metrics = useQuery({ queryKey: ['metrics'], queryFn: api.metrics })
  const list = useQuery({
    queryKey: ['applications', status, q],
    queryFn: () => api.list({ status, q: q.trim() || undefined }),
    // Keep polling while something is still being processed.
    refetchInterval: (query) => (query.state.data?.some((a) => a.status === 'received') ? 2000 : false),
  })
  const m = metrics.data

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Applications</h1>
          <p className="mt-1 text-sm text-stone-500">Broker submissions, read by AI and checked against credit policy.</p>
        </div>
        <div className="flex items-center gap-3"><UploadButton /></div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Awaiting review" value={m?.awaiting_review ?? '–'} />
        <Stat label="Awaiting approval" value={m?.pending_approval ?? '–'} />
        <Stat label="Approved, last 7 days" value={m?.approved_last_7_days ?? '–'} />
        <Stat label="Average confidence"
              value={m?.average_confidence != null ? `${Math.round(m.average_confidence * 100)}%` : '–'}
              hint="Lowest required field, per application" />
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-4 py-3">
          <div className="no-scrollbar -mx-1 flex gap-1 overflow-x-auto">
            {TABS.map((t, i) => (
              <button key={t.label} onClick={() => setTab(i)}
                      className={clsx('whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors',
                                      i === tab ? 'bg-stone-100 font-medium text-stone-900' : 'text-stone-500 hover:text-stone-900')}>
                {t.label}
              </button>
            ))}
          </div>
          <label className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search borrower or reference"
                   className="h-9 w-full rounded-lg border border-stone-200 bg-white pl-9 pr-3 text-sm outline-none placeholder:text-stone-400 focus:border-ink-500" />
          </label>
        </div>

        {/* Phones: a compact list instead of a wide table */}
        <ul className="divide-y divide-stone-100 sm:hidden">
          {list.data?.map((a) => (
            <li key={a.id} onClick={() => navigate(`/applications/${a.id}`)}
                className="cursor-pointer px-4 py-3.5 active:bg-stone-50">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-stone-900">{a.borrower_name ?? 'Reading document…'}</div>
                  <div className="mt-0.5 text-xs text-stone-500">
                    {moneyShort(a.loan_amount)} · LVR {percent(a.calculated_lvr)}
                  </div>
                </div>
                <StatusBadge status={a.status} />
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-stone-400">{a.reference}</span>
                <RiskDots app={a} />
              </div>
            </li>
          ))}
        </ul>

        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs text-stone-500">
                <th className="px-4 py-3 font-medium">Borrower</th>
                <th className="px-4 py-3 text-right font-medium">Amount</th>
                <th className="hidden px-4 py-3 font-medium lg:table-cell">Purpose</th>
                <th className="px-4 py-3 text-right font-medium">LVR</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">Confidence</th>
                <th className="px-4 py-3 font-medium">Open risks</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="hidden px-4 py-3 text-right font-medium lg:table-cell">Received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {list.data?.map((a) => (
                <tr key={a.id} onClick={() => navigate(`/applications/${a.id}`)}
                    className="cursor-pointer transition-colors hover:bg-stone-50/80">
                  <td className="px-4 py-3.5">
                    <div className="font-medium text-stone-900">{a.borrower_name ?? 'Reading document…'}</div>
                    <div className="mt-0.5 text-xs text-stone-400">{a.reference}</div>
                  </td>
                  <td className="px-4 py-3.5 text-right tabular-nums">{moneyShort(a.loan_amount)}</td>
                  <td className="hidden px-4 py-3.5 text-stone-600 lg:table-cell">
                    {a.loan_purpose ? optionLabel(a.loan_purpose) : '—'}
                    {a.property_type && <span className="text-stone-400"> · {optionLabel(a.property_type)}</span>}
                  </td>
                  <td className="px-4 py-3.5 text-right tabular-nums">{percent(a.calculated_lvr)}</td>
                  <td className="hidden px-4 py-3.5 md:table-cell"><ConfidenceBar value={a.overall_confidence} /></td>
                  <td className="px-4 py-3.5"><RiskDots app={a} /></td>
                  <td className="px-4 py-3.5"><StatusBadge status={a.status} /></td>
                  <td className="hidden px-4 py-3.5 text-right text-xs text-stone-500 lg:table-cell">{relative(a.received_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {list.isLoading && <Loading failures={list.failureCount} className="py-16" />}
        {list.data?.length === 0 && (
          <div className="py-16 text-center text-sm text-stone-500">No applications here.</div>
        )}
        {list.isError && (
          <div className="py-16 text-center text-sm text-red-600">Couldn't reach the API: {list.error.message}</div>
        )}
      </Card>
    </div>
  )
}
