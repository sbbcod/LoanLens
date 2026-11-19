import type { Severity } from '../api/types'

export const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-red-500',
  warning: 'bg-amber-400',
  info: 'bg-stone-300',
}
