import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { ArrowLeft, Send, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import { api, pdfUrl } from '../api/client'
import type { ApplicationDetail, FieldValue, Risk } from '../api/types'
import { Activity } from '../components/Activity'
import { FieldList } from '../components/FieldList'
import type { LayoutContext } from '../components/Layout'
import { PdfViewer } from '../components/PdfViewer'
import { RiskList } from '../components/RiskList'
import { Button, Card, ConfidenceBar, SectionTitle, Spinner, StatusBadge } from '../components/ui'
import { date, money, percent } from '../lib/format'
import { useSession } from '../lib/session'

const LOCKED = new Set(['pending_approval', 'approved', 'declined'])

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-stone-500">{label}</div>
      <div className="mt-0.5 text-[15px] font-medium tabular-nums text-stone-900">{children}</div>
    </div>
  )
}

/** Plays the credit manager's part when the Teams approval flow isn't connected. */
function SimulatedDecision({ app }: { app: ApplicationDetail }) {
  const queryClient = useQueryClient()
  const [comment, setComment] = useState('')
  const decide = useMutation({
    mutationFn: (d: 'approved' | 'declined') => api.decide(app.id, d, 'Tom (credit manager)', comment),
    onSuccess: () => void queryClient.invalidateQueries(),
  })
  return (
    <Card className="border-violet-200 bg-violet-50/40 p-4">
      <p className="text-sm font-medium text-violet-900">Waiting for the credit manager</p>
      <p className="mt-1 text-xs text-violet-800/70">
        Teams isn't connected in this demo, so you can play the manager's part here.
        With Power Automate connected, this decision arrives from a Teams approval card.
      </p>
      <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment (optional)"
             className="mt-3 h-9 w-full rounded-lg border border-violet-200 bg-white px-3 text-sm outline-none focus:border-violet-400" />
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={decide.isPending} onClick={() => decide.mutate('approved')}>Approve</Button>
        <Button disabled={decide.isPending} onClick={() => decide.mutate('declined')}>Decline</Button>
      </div>
    </Card>
  )
}

export function ReviewPage() {
  const { id = '' } = useParams()
  const session = useSession()
  const { requestUnlock } = useOutletContext<LayoutContext>()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)
  const [comment, setComment] = useState('')

  const query = useQuery({
    queryKey: ['application', id],
    queryFn: () => api.get(id),
    refetchInterval: (q) => (q.state.data?.status === 'received' ? 1500 : false),
  })

  const onUpdated = (detail: ApplicationDetail) => {
    queryClient.setQueryData(['application', id], detail)
    void queryClient.invalidateQueries({ queryKey: ['applications'] })
    void queryClient.invalidateQueries({ queryKey: ['metrics'] })
  }
  const edit = useMutation({
    mutationFn: ({ name, value }: { name: string; value: FieldValue }) => api.editFields(id, { [name]: value }),
    onSuccess: onUpdated,
  })
  const ack = useMutation({
    mutationFn: (r: Risk) => api.acknowledge(id, r.id, !r.acknowledged),
    onSuccess: onUpdated,
  })
  const submit = useMutation({ mutationFn: () => api.submit(id, comment), onSuccess: onUpdated })

  const app = query.data
  if (query.isLoading) return <div className="flex justify-center py-32"><Spinner /></div>
  if (!app) return <p className="py-32 text-center text-sm text-stone-500">Application not found.</p>

  const locked = LOCKED.has(app.status)
  const canEdit = !!session && !locked
  const openCritical = app.risks.filter((r) => r.severity === 'critical' && !r.acknowledged).length
  const decided = app.approvals.find((a) => a.decision)
  const error = edit.error ?? ack.error ?? submit.error
  const lvrOver = app.calculated_lvr != null && app.lvr_limit != null && app.calculated_lvr > app.lvr_limit

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-900">
          <ArrowLeft className="size-3.5" /> Applications
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{app.borrower_name ?? 'Reading document…'}</h1>
              <StatusBadge status={app.status} />
            </div>
            <p className="mt-1 text-sm text-stone-500">
              {app.reference} · received {date(app.received_at)}{app.sender_email && ` from ${app.sender_email}`}
            </p>
          </div>
        </div>
      </div>

      {app.status === 'received' && (
        <Card className="flex items-center gap-3 p-5 text-sm text-stone-600"><Spinner /> Reading the document and checking it against policy…</Card>
      )}
      {app.status === 'error' && (
        <Card className="border-red-200 bg-red-50/50 p-5 text-sm text-red-800">{app.error_message}</Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        {/* Left: the document */}
        <Card className="h-[70vh] overflow-hidden lg:sticky lg:top-20 lg:h-[calc(100vh-7rem)]">
          <PdfViewer url={pdfUrl(app.id)} page={page} onPageChange={setPage} />
        </Card>

        {/* Right: what the AI found, and what to do about it */}
        <div className="space-y-6">
          {app.status !== 'received' && app.status !== 'error' && (
            <>
              <Card className="grid grid-cols-2 gap-5 p-5 sm:grid-cols-4">
                <Figure label="Loan amount">{money(app.loan_amount)}</Figure>
                <Figure label="LVR">
                  <span className={clsx(lvrOver && 'text-red-600')}>{percent(app.calculated_lvr)}</span>
                  {app.lvr_limit != null && <span className="ml-1 text-xs font-normal text-stone-400">/ {app.lvr_limit}% max</span>}
                </Figure>
                <Figure label="Confidence"><ConfidenceBar value={app.overall_confidence} width="w-12" /></Figure>
                <Figure label="AI cost">${app.ai_cost_usd.toFixed(3)}</Figure>
              </Card>

              {app.summary && (
                <div className="flex gap-3 rounded-xl bg-ink-50/70 px-5 py-4">
                  <Sparkles className="mt-0.5 size-4 shrink-0 text-ink-500" />
                  <div>
                    <p className="text-sm leading-relaxed text-stone-700">{app.summary}</p>
                    <p className="mt-1.5 text-xs text-stone-400">AI summary. Figures below are checked against the document.</p>
                  </div>
                </div>
              )}

              <section>
                <SectionTitle aside={
                  <span className="text-xs text-stone-400">
                    {app.risks.filter((r) => !r.acknowledged).length} open
                  </span>}>
                  Risks
                </SectionTitle>
                <Card><RiskList risks={app.risks} canEdit={canEdit} busy={ack.isPending} onToggle={(r) => ack.mutate(r)} /></Card>
              </section>

              <section>
                <SectionTitle aside={
                  <span className="text-xs text-stone-400">{canEdit ? 'Click a value to see its source; hover to correct' : 'Click a value to see its source'}</span>}>
                  Extracted details
                </SectionTitle>
                <Card>
                  <FieldList fields={app.fields} selected={selected} canEdit={canEdit} saving={edit.isPending}
                             onSelect={(f) => { setSelected(selected === f.name ? null : f.name); if (f.page) setPage(f.page) }}
                             onSave={(name, value) => edit.mutateAsync({ name, value })} />
                </Card>
              </section>

              {/* Decision */}
              <section>
                <SectionTitle>Decision</SectionTitle>
                {app.status === 'pending_approval' ? (
                  <SimulatedDecision app={app} />
                ) : decided ? (
                  <Card className={clsx('p-4', decided.decision === 'approved' ? 'border-emerald-200 bg-emerald-50/50' : 'bg-stone-50')}>
                    <p className="text-sm font-medium">
                      {decided.decision === 'approved' ? 'Approved' : 'Declined'} by {decided.approver}
                    </p>
                    {decided.comment && <p className="mt-1 text-sm text-stone-600">“{decided.comment}”</p>}
                    <p className="mt-1 text-xs text-stone-400">{decided.decided_at && date(decided.decided_at)}</p>
                  </Card>
                ) : (
                  <Card className="p-4">
                    <p className="text-sm text-stone-600">
                      A credit manager makes the decision. Send it once the details are checked and critical risks acknowledged.
                    </p>
                    {session ? (
                      <>
                        <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2}
                                  placeholder="Note for the credit manager (optional)"
                                  className="mt-3 w-full resize-none rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-ink-500" />
                        <div className="mt-3 flex flex-wrap items-center gap-3">
                          <Button variant="primary" disabled={openCritical > 0 || submit.isPending} onClick={() => submit.mutate()}>
                            <Send className="size-3.5" /> Send for approval
                          </Button>
                          {openCritical > 0 && (
                            <span className="text-xs text-red-700">
                              Acknowledge {openCritical} critical risk{openCritical > 1 ? 's' : ''} first.
                            </span>
                          )}
                        </div>
                      </>
                    ) : (
                      <Button className="mt-3" onClick={requestUnlock}>Sign in to review</Button>
                    )}
                  </Card>
                )}
                {error && <p className="mt-2 text-sm text-red-600">{error.message}</p>}
              </section>
            </>
          )}

          <section>
            <SectionTitle>Activity</SectionTitle>
            <Card><Activity entries={app.audit} /></Card>
          </section>
        </div>
      </div>
    </div>
  )
}
