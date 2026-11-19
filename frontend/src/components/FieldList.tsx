import { clsx } from 'clsx'
import { Check, Pencil, Quote, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { Field, FieldValue } from '../api/types'
import { fieldValue, optionLabel } from '../lib/format'
import { ConfidenceBar } from './ui'

const OPTIONS: Record<string, string[]> = {
  borrower_type: ['company', 'trust', 'individual', 'smsf'],
  loan_purpose: ['purchase', 'refinance', 'construction', 'equity_release', 'bridging'],
  property_type: ['office', 'retail', 'industrial', 'residential_dev', 'land', 'mixed_use'],
}

function Editor({ field, onSave, onCancel, saving }: {
  field: Field
  onSave: (v: FieldValue) => void
  onCancel: () => void
  saving: boolean
}) {
  const [draft, setDraft] = useState(field.value == null ? '' : String(field.value))
  const numeric = ['money', 'percent', 'integer'].includes(field.kind)
  const input = 'h-8 w-full rounded-md border border-stone-300 bg-white px-2 text-sm outline-none focus:border-ink-500'

  function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = draft.trim()
    onSave(trimmed === '' ? null : numeric ? Number(trimmed) : trimmed)
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      {field.kind === 'enum' ? (
        <select autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} className={input}>
          <option value="">—</option>
          {OPTIONS[field.name]?.map((o) => <option key={o} value={o}>{optionLabel(o)}</option>)}
        </select>
      ) : (
        <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} className={input}
               type={field.kind === 'date' ? 'date' : numeric ? 'number' : 'text'} step="any"
               onKeyDown={(e) => e.key === 'Escape' && onCancel()} />
      )}
      <button type="submit" disabled={saving} aria-label="Save"
              className="rounded-md bg-ink-700 p-1.5 text-white hover:bg-ink-900 disabled:opacity-40">
        <Check className="size-3.5" />
      </button>
      <button type="button" onClick={onCancel} aria-label="Cancel"
              className="rounded-md p-1.5 text-stone-500 hover:bg-stone-100">
        <X className="size-3.5" />
      </button>
    </form>
  )
}

export function FieldList({ fields, selected, onSelect, canEdit, onSave, saving }: {
  fields: Field[]
  selected: string | null
  onSelect: (f: Field) => void
  canEdit: boolean
  onSave: (name: string, v: FieldValue) => Promise<unknown>
  saving: boolean
}) {
  const [editing, setEditing] = useState<string | null>(null)

  return (
    <ul className="divide-y divide-stone-100">
      {fields.map((f) => {
        const isOpen = selected === f.name
        const doubtful = !f.edited && (!f.grounded || f.confidence < 0.75)
        return (
          <li key={f.name}
              className={clsx('cursor-pointer px-4 py-3 transition-colors',
                              isOpen ? 'bg-ink-50/60' : 'hover:bg-stone-50')}
              onClick={() => onSelect(f)}>
            <div className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1">
              <div className="flex items-center gap-1.5 text-[13px] text-stone-500">
                {doubtful && <span className="size-1.5 shrink-0 rounded-full bg-amber-400" title="Needs a look" />}
                <span className="truncate">{f.label}</span>
                {f.required && <span className="text-stone-300" title="Required">*</span>}
              </div>

              <div className="min-w-0">
                {editing === f.name ? (
                  <Editor field={f} saving={saving} onCancel={() => setEditing(null)}
                          onSave={(v) => { void onSave(f.name, v).then(() => setEditing(null)) }} />
                ) : (
                  <div className="group flex items-center gap-2">
                    <span className={clsx('truncate text-sm', f.value == null ? 'text-stone-400' : 'text-stone-900')}>
                      {fieldValue(f.kind, f.value, f.name)}
                    </span>
                    {canEdit && (
                      <button onClick={(e) => { e.stopPropagation(); setEditing(f.name) }} aria-label={`Edit ${f.label}`}
                              className="rounded p-1 text-stone-400 opacity-0 transition-opacity hover:bg-stone-100 hover:text-stone-700 focus:opacity-100 group-hover:opacity-100">
                        <Pencil className="size-3" />
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end">
                {f.edited ? (
                  <span className="rounded-full bg-ink-50 px-2 py-0.5 text-[11px] font-medium text-ink-700">Corrected</span>
                ) : f.value == null ? (
                  <span className="text-[11px] text-stone-400">Not found</span>
                ) : (
                  <ConfidenceBar value={f.confidence} width="w-12" />
                )}
              </div>
            </div>

            {isOpen && (
              <div className="mt-3 space-y-2 pl-0 text-[13px] sm:pl-[10rem]">
                {f.evidence ? (
                  <figure className="flex gap-2 text-stone-600">
                    <Quote className="mt-0.5 size-3.5 shrink-0 text-stone-300" />
                    <blockquote>
                      “{f.evidence}”
                      {f.page && <span className="ml-1.5 text-stone-400">p.{f.page}</span>}
                    </blockquote>
                  </figure>
                ) : f.value != null ? (
                  <p className="text-stone-500">No supporting quote.</p>
                ) : (
                  <p className="text-stone-500">The document doesn't state this.</p>
                )}
                {!f.grounded && !f.edited && (
                  <p className="text-amber-700">The quote couldn't be found in the document. Check this value by hand.</p>
                )}
                {f.edited && (
                  <p className="text-stone-500">
                    AI read <span className="text-stone-700">{fieldValue(f.kind, f.ai_value, f.name)}</span>
                    {f.edited_by && <> · corrected by {f.edited_by.replace('user:', '')}</>}
                  </p>
                )}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
