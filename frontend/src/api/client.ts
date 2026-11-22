import type { ApplicationDetail, ApplicationSummary, FieldValue, Metrics, Status } from './types'
import { getSession, setSession } from '../lib/session'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function writeHeaders(): Record<string, string> {
  const session = getSession()
  return session ? { 'X-API-Key': session.passcode, 'X-User-Name': session.name } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (response.status === 401 && getSession()) {
    // The saved passcode no longer works (mistyped, or changed on the server).
    // Drop it so the page goes back to read-only instead of failing on every click.
    setSession(null)
    throw new ApiError(401, 'The passcode was not accepted. Sign in again to make changes.')
  }
  if (!response.ok) {
    let message = response.statusText
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
        message = body.detail
      }
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

function send<T>(path: string, method: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json', ...writeHeaders() },
    body: JSON.stringify(body),
  })
}

export const pdfUrl = (id: string) => `${BASE}/api/applications/${id}/pdf`

export const api = {
  list: (params: { status?: Status; q?: string } = {}) => {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    if (params.q) search.set('q', params.q)
    const qs = search.toString()
    return request<ApplicationSummary[]>(`/api/applications${qs ? `?${qs}` : ''}`)
  },
  get: (id: string) => request<ApplicationDetail>(`/api/applications/${id}`),
  metrics: () => request<Metrics>('/api/metrics'),
  policy: () => fetch(`${BASE}/api/policy`).then((r) => r.text()),
  /** True if the server accepts this passcode; checked before it is saved. */
  checkPasscode: async (passcode: string) => {
    const response = await fetch(`${BASE}/api/auth/check`, { headers: { 'X-API-Key': passcode } })
    if (response.status === 401) return false
    if (!response.ok) throw new ApiError(response.status, response.statusText)
    return true
  },

  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    form.append('source', 'upload')
    return request<{ id: string; reference: string }>('/api/ingest', {
      method: 'POST',
      headers: writeHeaders(),
      body: form,
    })
  },
  editFields: (id: string, changes: Record<string, FieldValue>) =>
    send<ApplicationDetail>(`/api/applications/${id}/fields`, 'PATCH', { changes }),
  acknowledge: (id: string, riskId: number, acknowledged: boolean) =>
    send<ApplicationDetail>(`/api/applications/${id}/acknowledge-risk`, 'POST', {
      risk_id: riskId,
      acknowledged,
    }),
  submit: (id: string, comment: string) =>
    send<ApplicationDetail>(`/api/applications/${id}/submit-for-approval`, 'POST', {
      comment: comment || null,
    }),
  /** Demo only: plays the credit manager's part when no Power Automate flow is connected. */
  decide: (id: string, decision: 'approved' | 'declined', approver: string, comment: string) =>
    send(`/api/approvals/callback`, 'POST', {
      application_id: id,
      decision,
      approver,
      comment: comment || null,
      flow_run_id: 'simulated',
    }),
}
