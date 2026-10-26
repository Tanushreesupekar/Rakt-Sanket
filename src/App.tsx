import { useEffect, useState } from 'react'
import { api, clearSession, getSessionUser, hasSessionToken } from './lib/api'
import type { AuthUser } from './lib/types'
import AuthGate from './auth/AuthGate'
import Landing from './pages/Landing'
import UserPage from './donor/UserPage'
import AdminApp from './admin/AdminApp'

const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED === 'true'

function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => AUTH_REQUIRED ? getSessionUser() : null)
  const [sessionReady, setSessionReady] = useState(!AUTH_REQUIRED)
  const [authMode, setAuthMode] = useState<'admin' | 'donor' | null>(null)

  useEffect(() => {
    if (!AUTH_REQUIRED) return
    if (!hasSessionToken()) {
      setAuthUser(null)
      setSessionReady(true)
      return
    }
    let active = true
    api.currentUser().then((user) => {
      if (!active) return
      setAuthUser(user)
    }).catch(() => {
      clearSession()
      if (active) setAuthUser(null)
    }).finally(() => { if (active) setSessionReady(true) })
    return () => { active = false }
  }, [])

  function handleAuthenticated(user: AuthUser) {
    setAuthUser(user)
    setAuthMode(null)
  }

  function signOut() {
    clearSession()
    setAuthUser(null)
    setAuthMode(null)
  }

  if (AUTH_REQUIRED && !sessionReady) return <div className="auth-loading"><span className="spinner" />Verifying session…</div>
  if (!AUTH_REQUIRED) {
    return <AdminApp user={null} onSignOut={signOut} />
  }
  if (!authUser && authMode == null) {
    return <Landing onAdmin={() => setAuthMode('admin')} onDonor={() => setAuthMode('donor')} />
  }
  if (!authUser) return <AuthGate roleHint={authMode} onBack={() => setAuthMode(null)} onAuthenticated={handleAuthenticated} />
  if (authUser.role === 'donor') {
    return <UserPage user={authUser} donors={[]} onRefresh={() => {}} onSignOut={signOut} onHome={signOut} />
  }
  return <AdminApp user={authUser} onSignOut={signOut} />
}

export default App
