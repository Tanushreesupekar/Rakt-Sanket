import { useState, type FormEvent } from 'react'
import { Droplet, LockKeyhole, ShieldCheck } from 'lucide-react'
import { api, saveSession } from './api'
import type { AuthUser } from './types'

export default function AuthGate({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const form = new FormData(event.currentTarget)
    try {
      const session = await api.login(String(form.get('email')), String(form.get('password')))
      saveSession(session)
      onAuthenticated(session.user)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed. Check your credentials and try again.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-page"><section className="auth-panel"><a className="brand auth-brand" href="#signin"><span className="brand-mark"><Droplet size={21} fill="currentColor" /></span><span className="brand-copy"><strong>RaktSanket</strong><small>Blood operations</small></span></a><div className="auth-heading"><span className="auth-icon"><LockKeyhole size={18} /></span><div className="eyebrow">SECURE ACCESS</div><h1>Sign in to RaktSanket</h1><p>Use the account provided by your blood bank administrator.</p></div>{error && <div className="error-banner">{error}</div>}<form className="auth-form" onSubmit={signIn}><label>Email address<input name="email" type="email" autoComplete="username" maxLength={254} required /></label><label>Password<input name="password" type="password" autoComplete="current-password" minLength={12} maxLength={128} required /></label><button className="button button-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in securely'}</button></form><p className="auth-footnote"><ShieldCheck size={14} />Your account permissions determine the workspace you can access.</p></section></main>
}
