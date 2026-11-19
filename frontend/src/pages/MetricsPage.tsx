import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import type { Status } from '../api/types'
import { Card, SectionTitle, Spinner, Stat } from '../components/ui'
import { STATUS_LABEL } from '../lib/format'

const BAR = '#2c4a6e' // ink-600: the single series colour

const ORDER: Status[] = ['needs_review', 'extracted', 'pending_approval', 'approved', 'declined', 'error']

function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}

export function MetricsPage() {
  const { data: m, isLoading } = useQuery({ queryKey: ['metrics'], queryFn: api.metrics })
  if (isLoading || !m) return <div className="flex justify-center py-32"><Spinner /></div>

  const pct = (v: number | null) => (v == null ? '–' : `${Math.round(v * 100)}%`)
  const statusMax = Math.max(1, ...ORDER.map((s) => m.by_status[s] ?? 0))

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Metrics</h1>
        <p className="mt-1 text-sm text-stone-500">
          How much the AI is trusted, how often people correct it, and what it costs.
          Model: <span className="text-stone-700">{m.llm_model}</span>
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Applications" value={m.total} />
        <Stat label="Corrected by a person" value={pct(m.human_edit_rate)}
              hint="Share of AI-read values changed in review" />
        <Stat label="AI cost per application"
              value={m.average_cost_usd == null ? '–' : `$${m.average_cost_usd.toFixed(3)}`}
              hint={m.llm_provider === 'mock' ? 'Mock provider: no real calls' : 'Both model calls, in USD'} />
        <Stat label="AI time per application"
              value={m.average_latency_s == null ? '–' : `${m.average_latency_s.toFixed(1)}s`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section>
          <SectionTitle>Applications received, last 14 days</SectionTitle>
          <Card className="px-3 pb-3 pt-5">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={m.daily} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid vertical={false} stroke="#f0eeec" />
                  <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={false}
                         tick={{ fontSize: 11, fill: '#a8a29e' }} interval="preserveStartEnd" minTickGap={24} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false}
                         tick={{ fontSize: 11, fill: '#a8a29e' }} width={40} />
                  <Tooltip cursor={{ fill: '#f5f5f4' }}
                           content={({ active, payload, label }) =>
                             active && payload?.length ? (
                               <div className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs shadow-sm">
                                 <div className="text-stone-500">{shortDate(String(label))}</div>
                                 <div className="mt-0.5 font-medium text-stone-900">{payload[0].value} received</div>
                               </div>
                             ) : null} />
                  <Bar dataKey="count" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </section>

        <section>
          <SectionTitle>By status</SectionTitle>
          <Card className="space-y-3.5 p-5">
            {ORDER.map((s) => {
              const n = m.by_status[s] ?? 0
              return (
                <div key={s}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-stone-600">{STATUS_LABEL[s]}</span>
                    <span className="tabular-nums text-stone-900">{n}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-stone-100">
                    <div className="h-full rounded-full" style={{ width: `${(n / statusMax) * 100}%`, background: BAR }} />
                  </div>
                </div>
              )
            })}
          </Card>
        </section>
      </div>

      <Card className="p-5 text-sm leading-relaxed text-stone-600">
        <p className="font-medium text-stone-900">How to read these</p>
        <p className="mt-1">
          A rising correction rate means the AI is reading documents worse, or brokers have changed their formats.
          Cost and time are measured on every model call, so model choices can be compared on real numbers.
          Field-level accuracy is measured separately against a labelled sample set; see the evaluation results in the repository.
        </p>
      </Card>
    </div>
  )
}
