import { clsx } from 'clsx'
import { Lock, LockOpen } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import { setSession, useSession } from '../lib/session'
import { Button } from './ui'

function UnlockDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [passcode, setPasscode] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setChecking(true)
    setError(null)
    try {
      if (await api.checkPasscode(passcode.trim())) {
        setSession({ name: name.trim() || 'Analyst', passcode: passcode.trim() })
        onClose()
      } else {
        setError("That passcode isn't right.")
      }
    } catch {
      setError("Couldn't reach the server. The demo may be waking up; try again in a moment.")
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-stone-900/20 px-4 pt-[18vh] backdrop-blur-[2px]"
         onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm rounded-2xl border border-stone-200 bg-white p-6 shadow-xl shadow-stone-900/5">
        <h2 className="text-base font-semibold">Sign in to review</h2>
        <p className="mt-1 text-sm text-stone-500">
          Viewing is open. Editing, uploading and approving need the demo passcode.
        </p>
        <label className="mt-5 block text-sm font-medium text-stone-700">
          Your name
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Sarah"
                 className="mt-1.5 block h-10 w-full rounded-lg border border-stone-200 px-3 text-sm outline-none focus:border-ink-500" />
        </label>
        <label className="mt-3 block text-sm font-medium text-stone-700">
          Passcode
          <input type="password" value={passcode} required
                 onChange={(e) => { setPasscode(e.target.value); setError(null) }}
                 aria-invalid={!!error} aria-describedby={error ? 'unlock-error' : undefined}
                 className={clsx('mt-1.5 block h-10 w-full rounded-lg border px-3 text-sm outline-none focus:border-ink-500',
                                 error ? 'border-red-300' : 'border-stone-200')} />
        </label>
        {error && <p id="unlock-error" role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={checking}>{checking ? 'Checking…' : 'Continue'}</Button>
        </div>
      </form>
    </div>
  )
}

export function Layout() {
  const session = useSession()
  const [unlocking, setUnlocking] = useState(false)

  const link = ({ isActive }: { isActive: boolean }) =>
    clsx('rounded-md px-3 py-1.5 text-sm transition-colors',
         isActive ? 'bg-stone-100 font-medium text-stone-900' : 'text-stone-500 hover:text-stone-900')

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-stone-200/80 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <NavLink to="/" className="flex shrink-0 items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-6" />
            <span className="hidden text-[15px] font-semibold tracking-tight min-[400px]:inline">LoanLens</span>
          </NavLink>
          <nav className="flex items-center gap-0.5 sm:gap-1">
            <NavLink to="/" end className={link}>Applications</NavLink>
            <NavLink to="/metrics" className={link}>Metrics</NavLink>
          </nav>
          <div className="ml-auto shrink-0">
            {session ? (
              <button onClick={() => setSession(null)} title="Sign out"
                      className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 text-sm text-stone-600 hover:bg-stone-100 sm:pr-3">
                <span className="flex size-7 items-center justify-center rounded-full bg-ink-700 text-xs font-medium text-white">
                  {session.name.slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden sm:inline">{session.name}</span>
                <LockOpen className="size-3.5 text-stone-400" />
              </button>
            ) : (
              <Button variant="ghost" onClick={() => setUnlocking(true)} title="Sign in to edit">
                <Lock className="size-3.5" /> <span className="hidden sm:inline">Read-only</span>
              </Button>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6">
        <Outlet context={{ requestUnlock: () => setUnlocking(true) }} />
      </main>
      {unlocking && <UnlockDialog onClose={() => setUnlocking(false)} />}
    </div>
  )
}

export interface LayoutContext {
  requestUnlock: () => void
}
