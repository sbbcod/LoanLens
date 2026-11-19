// The demo has no user accounts. A reviewer types their name and the demo
// passcode once; both are remembered in this browser only.

import { useSyncExternalStore } from 'react'

export interface Session {
  name: string
  passcode: string
}

const KEY = 'loanlens.session'
const listeners = new Set<() => void>()

function read(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

let current = read()

export const getSession = () => current

export function setSession(session: Session | null) {
  current = session
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session))
    else localStorage.removeItem(KEY)
  } catch {
    /* storage blocked: session lasts for this page only */
  }
  listeners.forEach((l) => l())
}

export function useSession(): Session | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => current,
  )
}
