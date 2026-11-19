import { useState, type FormEvent } from 'react'
import { Droplet, Gauge, HeartPulse, LockKeyhole, ShieldCheck, UserPlus } from 'lucide-react'
import { api, saveSession } from '../lib/api'
import type { AuthUser } from '../lib/types'

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

export default function AuthGate({ onAuthenticated, roleHint, onBack }: { onAuthenticated: (user: AuthUser, chosenWorkspace?: 'admin' | 'donor') => void; roleHint?: 'admin' | 'donor' | null; onBack?: () => void }) {
  const [targetRole, setTargetRole] = useState<'admin' | 'donor'>(roleHint === 'donor' ? 'donor' : 'admin')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const isDonor = targetRole === 'donor'
  const registering = isDonor && mode === 'register'

  function fillDemoAdmin() {
    setEmail('admin@raktsanket.org')
    setPassword('AdminPassword123!')
    setError('')
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      let session = await api.login(email.trim(), password)
      
      // If user is logging into Admin Console but has a donor role, elevate in dev mode
      if (targetRole === 'admin' && session.user.role !== 'admin') {
        try {
          saveSession(session)
          session = await api.switchRole('admin')
        } catch {
          // If switch fails (e.g. strict production), continue with existing session
        }
      }

      saveSession(session)
      onAuthenticated(session.user, targetRole)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed. Check your credentials and try again.')
    } finally {
      setBusy(false)
    }
  }

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const form = new FormData(event.currentTarget)
      const regPassword = String(form.get('password'))
      if (regPassword !== String(form.get('confirm'))) throw new Error('The two passwords do not match.')
      if (form.get('consent') !== 'on') throw new Error('Please confirm that the blood bank may contact you about donation.')
      const session = await api.registerDonor({
        name: String(form.get('name')).trim(),
        email: String(form.get('email')).trim(),
        password: regPassword,
        district: String(form.get('district')).trim(),
        blood_group: String(form.get('blood_group')),
        age: Number(form.get('age')),
        last_donation_date: String(form.get('last_donation_date') ?? '') || null,
        donations_count: Number(form.get('donations_count')),
        consent: true,
      })
      saveSession(session)
      onAuthenticated(session.user, 'donor')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not create your donor account. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-page"><section className={`auth-panel ${registering ? 'auth-panel-wide' : ''}`}>
    <a className="brand auth-brand" href="#signin" onClick={(event) => { event.preventDefault(); onBack?.() }}>
      <span className="brand-mark"><Droplet size={21} fill="currentColor" /></span>
      <span className="brand-copy"><strong>RaktSanket</strong><small>Blood operations</small></span>
    </a>

    <div className="auth-tabs" role="tablist" aria-label="Choose workspace to access">
      <button
        type="button"
        role="tab"
        aria-selected={targetRole === 'admin'}
        className={`auth-tab ${targetRole === 'admin' ? 'auth-tab-active' : ''}`}
        onClick={() => { setTargetRole('admin'); setMode('signin'); setError('') }}
      >
        <Gauge size={13} style={{ display: 'inline', marginRight: 5, verticalAlign: -1 }} />
        Admin Console
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={targetRole === 'donor'}
        className={`auth-tab ${targetRole === 'donor' ? 'auth-tab-active' : ''}`}
        onClick={() => { setTargetRole('donor'); setError('') }}
      >
        <HeartPulse size={13} style={{ display: 'inline', marginRight: 5, verticalAlign: -1 }} />
        Donor Portal
      </button>
    </div>

    {isDonor && <div className="auth-tabs auth-subtabs" role="tablist" aria-label="Donor access" style={{ marginTop: 8 }}>
      <button type="button" role="tab" aria-selected={mode === 'signin'} className={`auth-tab ${mode === 'signin' ? 'auth-tab-active' : ''}`} onClick={() => { setMode('signin'); setError('') }}>Sign in</button>
      <button type="button" role="tab" aria-selected={mode === 'register'} className={`auth-tab ${mode === 'register' ? 'auth-tab-active' : ''}`} onClick={() => { setMode('register'); setError('') }}>Create account</button>
    </div>}

    <div className={`auth-heading ${isDonor ? 'auth-heading-tabs' : ''}`}>
      <span className="auth-icon">{registering ? <UserPlus size={18} /> : <LockKeyhole size={18} />}</span>
      <div className="eyebrow">{registering ? 'NEW DONOR REGISTRATION' : isDonor ? 'DONOR SIGN IN' : 'ADMINISTRATOR SIGN IN'}</div>
      <h1>{registering ? 'Create your donor account' : isDonor ? 'Welcome back, donor' : 'Operator sign in'}</h1>
      <p>{registering ? 'Register once to manage availability, raise requests and receive email outreach from your district blood bank.' : isDonor ? 'Sign in to manage availability, blood requests and donation history.' : 'Sign in as a district blood bank administrator to manage inventory, forecasts, and review donor blood requests.'}</p>
    </div>

    {targetRole === 'admin' && (
      <div className="demo-credentials-banner">
        <div className="demo-creds-info">
          <ShieldCheck size={14} />
          <span>Demo Admin: <strong>admin@raktsanket.org</strong> / <strong>AdminPassword123!</strong></span>
        </div>
        <button type="button" className="button button-outline button-compact" onClick={fillDemoAdmin}>
          Auto-fill
        </button>
      </div>
    )}

    {error && <div className="error-banner">{error}</div>}

    {registering ? <form className="auth-form" onSubmit={register}>
      <label>Full name<input name="name" type="text" autoComplete="name" minLength={2} maxLength={120} required /></label>
      <label>Email address<input name="email" type="email" autoComplete="email" maxLength={254} required /></label>
      <div className="auth-form-row">
        <label>Password<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
        <label>Confirm password<input name="confirm" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
      </div>
      <div className="auth-form-row">
        <label>District<input name="district" type="text" autoComplete="address-level2" minLength={2} maxLength={80} placeholder="e.g. Amravati" required /></label>
        <label>Blood group<select name="blood_group" defaultValue="O+" required>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
      </div>
      <div className="auth-form-row">
        <label>Age<input name="age" type="number" min={18} max={65} defaultValue={29} required /></label>
        <label>Previous donations<input name="donations_count" type="number" min={0} max={200} defaultValue={0} required /></label>
      </div>
      <label>Last donation date (optional)<input name="last_donation_date" type="date" /></label>
      <label className="auth-consent"><input name="consent" type="checkbox" required /><span>I agree to be contacted by my district blood bank about blood donation and understand that my profile is used for donor outreach.</span></label>
      <button className="button button-primary" disabled={busy}>{busy ? 'Creating account…' : 'Create donor account'}</button>
      <button type="button" className="auth-switch" onClick={() => { setMode('signin'); setError('') }}>Already registered? Sign in instead</button>
      {onBack && <button type="button" className="button button-outline" onClick={onBack}>Back to home</button>}
    </form> : <form className="auth-form" onSubmit={signIn}>
      <label>Email address<input name="email" type="email" autoComplete="username" maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" minLength={12} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      <button className="button button-primary" disabled={busy}>{busy ? 'Signing in…' : `Sign in to ${targetRole === 'admin' ? 'Admin Console' : 'Donor Portal'}`}</button>
      {isDonor && <button type="button" className="auth-switch" onClick={() => { setMode('register'); setError('') }}>New donor? Create an account</button>}
      {onBack && <button type="button" className="button button-outline" onClick={onBack}>Back to home</button>}
    </form>}

    <p className="auth-footnote"><ShieldCheck size={14} />{registering ? 'Your account is separate from any imported donor record. Blood bank staff can review and update your profile.' : 'Your account permissions determine the workspace you can access.'}</p>
  </section></main>
}
