import { useEffect, useState, type FormEvent } from 'react'
import { Bell, CalendarDays, Check, Droplet, HeartPulse, History, MapPin, Send, ShieldCheck, UserRound, Users } from 'lucide-react'
import { api } from './api'
import type { BloodRequest, Donor, DonorHistory, DonorNotification } from './types'

type DonorSection = 'profile' | 'requests' | 'notifications' | 'history'
const sections: { id: DonorSection; label: string; icon: typeof UserRound }[] = [
  { id: 'profile', label: 'Profile', icon: UserRound },
  { id: 'requests', label: 'Blood requests', icon: HeartPulse },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'history', label: 'Donation history', icon: History },
]

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not recorded'
}

export default function DonorPortal({ donors, onRefresh, fixedDonorId }: { donors: Donor[]; onRefresh: () => void; fixedDonorId?: number | null }) {
  const [section, setSection] = useState<DonorSection>('profile')
  const [donorId, setDonorId] = useState('')
  const [profile, setProfile] = useState<Donor | null>(null)
  const [history, setHistory] = useState<DonorHistory | null>(null)
  const [requests, setRequests] = useState<BloodRequest[]>([])
  const [notifications, setNotifications] = useState<DonorNotification[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (fixedDonorId) {
      setDonorId(String(fixedDonorId))
    } else if (!donorId && donors.length) {
      setDonorId(String(donors[0].id))
    }
  }, [donorId, donors, fixedDonorId])

  useEffect(() => {
    if (!donorId) return
    let active = true
    const id = Number(donorId)
    Promise.all([api.donorProfile(id), api.donorHistory(id), api.bloodRequests(id), api.donorNotifications(id)])
      .then(([nextProfile, nextHistory, nextRequests, nextNotifications]) => {
        if (!active) return
        setProfile(nextProfile)
        setHistory(nextHistory)
        setRequests(nextRequests)
        setNotifications(nextNotifications)
        setError('')
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Could not load this donor record.')
      })
    return () => { active = false }
  }, [donorId])

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) return
    setBusy(true)
    setError('')
    const formElement = event.currentTarget
    try {
      const form = new FormData(formElement)
      const updated = await api.updateDonorProfile(profile.id, {
        name: String(form.get('name')),
        age: Number(form.get('age')),
        available: form.get('available') === 'on',
      })
      setProfile(updated)
      setMessage('Profile updated.')
      onRefresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not update profile.')
    } finally {
      setBusy(false)
    }
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) return
    setBusy(true)
    setError('')
    const formElement = event.currentTarget
    try {
      const form = new FormData(formElement)
      const created = await api.createBloodRequest({
        donor_id: profile.id,
        blood_group: String(form.get('blood_group')),
        units_requested: Number(form.get('units_requested')),
        hospital_name: String(form.get('hospital_name')),
        district: String(form.get('district')),
        needed_by: String(form.get('needed_by')),
        notes: String(form.get('notes')) || null,
      })
      setRequests((current) => [created, ...current])
      setMessage('Request submitted for review.')
      formElement.reset()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not submit the request.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="donor-workspace">
    <div className="donor-welcome"><div><div className="eyebrow"><span className="eyebrow-mark" />DONOR PORTAL <span className="eyebrow-divider">/</span> {fixedDonorId ? 'SIGNED-IN ACCOUNT' : 'DEMO ACCOUNT'}</div><h2>Your donor space</h2><p>Manage your availability and follow blood-related activity.</p></div>{!fixedDonorId && <label className="donor-account-picker"><Users size={15} /><select aria-label="Select demo donor account" value={donorId} onChange={(event) => { setDonorId(event.target.value); setMessage('') }}>{donors.map((donor) => <option key={donor.id} value={donor.id}>{donor.name.replace(' (demo)', '')} · {donor.blood_group}</option>)}</select></label>}</div>
    {error && <div className="error-banner"><span>{error}</span></div>}
    {message && <div className="success-banner"><Check size={15} />{message}<button onClick={() => setMessage('')} aria-label="Dismiss">×</button></div>}
    {!profile ? <div className="loading-state"><span className="spinner" />Loading donor record…</div> : <>
      <div className="donor-summary-strip"><span className="donor-large-avatar">{profile.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><div className="donor-summary-name"><strong>{profile.name.replace(' (demo)', '')}</strong><span><MapPin size={13} />{profile.district} district</span></div><span className="blood-type donor-blood-type">{profile.blood_group}</span><span className={`availability-chip ${profile.available ? 'available' : 'unavailable'}`}><i />{profile.available ? 'Available' : 'Taking a break'}</span></div>
      <div className="donor-content-grid">
        <nav className="donor-nav" aria-label="Donor navigation">{sections.map(({ id, label, icon: Icon }) => <button key={id} className={`donor-nav-item ${section === id ? 'donor-nav-active' : ''}`} onClick={() => { setSection(id); setMessage('') }}><Icon size={17} /><span>{label}</span>{id === 'notifications' && notifications.length > 0 && <small>{notifications.length}</small>}</button>)}</nav>
        <div className="donor-section-content">
          {section === 'profile' && <article className="panel donor-form-panel"><div className="panel-heading"><div><div className="eyebrow">PERSONAL DETAILS</div><h3>Donor profile</h3></div><ShieldCheck size={18} className="donor-panel-icon" /></div><form key={profile.id} className="donor-profile-form" onSubmit={saveProfile}><label>Full name<input name="name" defaultValue={profile.name.replace(' (demo)', '')} required /></label><div className="donor-form-pair"><label>Age<input name="age" type="number" min="18" max="65" defaultValue={profile.age} required /></label><label>Blood group<input value={profile.blood_group} readOnly /></label></div><div className="donor-readonly-row"><span>Last donation</span><strong>{formatDate(profile.last_donation_date)}</strong></div><div className="availability-setting"><span><strong>Available to be contacted</strong><small>Staff can include you in donor outreach rounds.</small></span><label className="switch"><input type="checkbox" name="available" defaultChecked={profile.available} /><span /></label></div><button className="button button-primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button></form></article>}
          {section === 'requests' && <div className="donor-request-layout"><article className="panel donor-form-panel"><div className="panel-heading"><div><div className="eyebrow">REQUEST BLOOD</div><h3>Submit a request</h3></div><HeartPulse size={18} className="donor-panel-icon" /></div><form key={profile.id} className="donor-profile-form" onSubmit={submitRequest}><label>Required blood group<select name="blood_group" defaultValue={profile.blood_group}><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select></label><div className="donor-form-pair"><label>Units needed<input name="units_requested" type="number" min="1" max="20" defaultValue="1" required /></label><label>Needed by<input name="needed_by" type="date" required /></label></div><label>Hospital<input name="hospital_name" placeholder="Hospital or blood bank" required /></label><label>District<input name="district" defaultValue={profile.district} required /></label><label>Additional details<textarea name="notes" rows={3} placeholder="Optional request details" /></label><button className="button button-primary" disabled={busy}><Send size={15} />{busy ? 'Submitting…' : 'Submit for review'}</button><p className="request-disclaimer">Requests are stored for operator review; this demo does not dispatch blood or emergency services.</p></form></article><article className="panel donor-requests-list"><div className="panel-heading"><div><div className="eyebrow">YOUR SUBMISSIONS</div><h3>Request history</h3></div><span className="record-count">{requests.length}</span></div>{requests.length ? requests.map((request) => <div className="donor-request-item" key={request.id}><span className="request-blood-type">{request.blood_group}</span><span className="request-item-main"><strong>{request.hospital_name}</strong><small>{request.units_requested} unit{request.units_requested > 1 ? 's' : ''} · {formatDate(request.needed_by)}</small></span><span className="request-status">{request.status}</span></div>) : <div className="donor-empty"><HeartPulse size={19} /><span>No blood requests yet.</span></div>}</article></div>}
          {section === 'notifications' && <article className="panel donor-activity-panel"><div className="panel-heading"><div><div className="eyebrow">DONOR UPDATES</div><h3>Notifications</h3></div><span className="record-count">{notifications.length}</span></div>{notifications.length ? notifications.map((item) => <div className="donor-notification-item" key={item.id}><span className="notification-icon"><Bell size={16} /></span><span className="notification-main"><strong>{item.blood_group} donor activation · {item.district}</strong><span>{item.message}</span><small><CalendarDays size={12} />{formatDate(item.created_at)} · Tier {item.stage} · {item.status}</small></span><span className="notification-score">{item.cbsri.toFixed(0)}<small>CBSRI</small></span></div>) : <div className="donor-empty"><Bell size={19} /><span>No notifications for this donor.</span></div>}<p className="request-disclaimer">These records are simulated campaign notifications. No SMS or email was sent.</p></article>}
          {section === 'history' && <article className="panel donor-history-panel"><div className="panel-heading"><div><div className="eyebrow">DONATION RECORD</div><h3>Donation history</h3></div><History size={18} className="donor-panel-icon" /></div><div className="history-stats-grid"><div><span>Total donations</span><strong>{history?.donations_count ?? profile.donations_count}</strong></div><div><span>Last donation</span><strong>{formatDate(history?.last_donation_date ?? profile.last_donation_date)}</strong></div><div><span>Days since donation</span><strong>{history?.donation_interval_days ?? '—'}</strong></div><div><span>Notifications received</span><strong>{history?.notifications_received ?? 0}</strong></div></div><div className="history-record"><span className="history-record-icon"><Droplet size={16} /></span><span><strong>Most recent donation</strong><small>{formatDate(history?.last_donation_date ?? profile.last_donation_date)}</small></span><span className="history-record-tag">SELF-REPORTED</span></div><p className="request-disclaimer">Donation history in this demo is a profile summary and should be confirmed by the blood bank.</p></article>}
        </div>
      </div>
    </>}
  </section>
}
