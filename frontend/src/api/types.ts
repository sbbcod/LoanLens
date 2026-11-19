// Mirrors backend/app/schemas.py. Keep the two in step.

export type Status =
  | 'received'
  | 'needs_review'
  | 'extracted'
  | 'reviewed'
  | 'pending_approval'
  | 'approved'
  | 'declined'
  | 'error'

export type Severity = 'critical' | 'warning' | 'info'
export type FieldKind = 'text' | 'money' | 'integer' | 'percent' | 'date' | 'enum'
export type FieldValue = string | number | null

export interface RiskCounts {
  critical: number
  warning: number
  info: number
}

export interface ApplicationSummary {
  id: string
  reference: string
  status: Status
  source: string
  borrower_name: string | null
  loan_amount: number | null
  loan_purpose: string | null
  property_type: string | null
  calculated_lvr: number | null
  overall_confidence: number | null
  needs_review: boolean
  open_risks: RiskCounts
  received_at: string
}

export interface Field {
  name: string
  label: string
  kind: FieldKind
  required: boolean
  value: FieldValue
  ai_value: FieldValue
  confidence: number
  evidence: string | null
  page: number | null
  grounded: boolean
  edited: boolean
  edited_by: string | null
  edited_at: string | null
}

export interface Risk {
  id: number
  source: 'rule' | 'llm' | 'system'
  code: string
  severity: Severity
  message: string
  policy_ref: string | null
  acknowledged: boolean
  acknowledged_by: string | null
}

export interface Approval {
  id: number
  requested_by: string
  requested_at: string
  approver: string | null
  decision: 'approved' | 'declined' | null
  comment: string | null
  decided_at: string | null
}

export interface AuditEntry {
  id: number
  actor: string
  action: string
  detail: Record<string, unknown> | null
  created_at: string
}

export interface ApplicationDetail extends ApplicationSummary {
  sender_email: string | null
  subject: string | null
  summary: string | null
  error_message: string | null
  lvr_limit: number | null
  ai_cost_usd: number
  fields: Field[]
  risks: Risk[]
  approvals: Approval[]
  audit: AuditEntry[]
}

export interface Metrics {
  total: number
  by_status: Partial<Record<Status, number>>
  awaiting_review: number
  pending_approval: number
  approved_last_7_days: number
  average_confidence: number | null
  human_edit_rate: number | null
  average_cost_usd: number | null
  average_latency_s: number | null
  daily: { date: string; count: number }[]
  llm_provider: string
  llm_model: string
}
