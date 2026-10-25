import { Droplet, LogOut, ShieldCheck } from 'lucide-react'
import DonorPortal from './DonorPortal'
import type { AuthUser, Donor } from '../lib/types'

export default function UserPage({
  user,
  donors,
  onRefresh,
  onSignOut,
  onHome,
}: {
  user: AuthUser
  donors: Donor[]
  onRefresh: () => void
  onSignOut: () => void
  onHome: () => void
}) {
  return (
    <div className="user-shell">
      <header className="user-topbar">
        <button className="brand brand-button" onClick={onHome} aria-label="Back to home">
          <span className="brand-mark"><Droplet size={20} fill="currentColor" /></span>
          <span className="brand-copy"><strong>RaktSanket</strong><small>Donor space</small></span>
        </button>
        <div className="user-account">
          <span className="user-email" title={user.email}>{user.email}</span>
          <span className="user-role">donor account</span>
          <button className="button button-outline button-compact" onClick={onSignOut}><LogOut size={14} /><span>Sign out</span></button>
        </div>
      </header>

      <main className="user-main">
        <div className="user-hero">
          <div>
            <div className="eyebrow"><span className="eyebrow-mark" />DONOR ACCESS · SIGNED-IN ACCOUNT</div>
            <h1>Welcome to your donor space</h1>
            <p>Keep your availability current, raise a blood request for review, and track outreach and donation history. Outreach here is simulated — no SMS is sent without operator review.</p>
          </div>
          <div className="user-hero-note"><ShieldCheck size={15} /><span>Eligibility (90-day interval, age 18–65) and consent are checked before any contact round.</span></div>
        </div>

        {user.donor_id == null ? (
          <div className="empty-state">
            <strong>No donor profile linked</strong>
            <span>Ask your blood-bank administrator to link this login to a donor record.</span>
          </div>
        ) : (
          <DonorPortal donors={donors} fixedDonorId={user.donor_id} onRefresh={onRefresh} />
        )}

        <footer className="page-footer user-footer">
          <span>RaktSanket · Donor space · Pilot</span>
          <span><ShieldCheck size={14} />Your availability controls whether staff can include you in outreach</span>
        </footer>
      </main>
    </div>
  )
}
