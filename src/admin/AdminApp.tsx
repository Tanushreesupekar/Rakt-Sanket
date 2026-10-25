import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowRight, Bell, Check, ChevronDown, Droplet, Gauge, HeartPulse, MapPin, Menu, Plus, RefreshCw,
  ShieldCheck, TriangleAlert, X,
} from 'lucide-react'
import { api } from '../lib/api'
import type { Advisory, AuthUser, Campaign, Dashboard, Donor, Inventory } from '../lib/types'
import DonorPortal from '../donor/DonorPortal'
import { adminNavigation, bloodGroups, Modal, pageDescription } from './components/shared'
import type { AdminView } from './components/shared'
import { Overview } from './views/Overview'
import { InventoryView } from './views/InventoryView'
import { ForecastView } from './views/ForecastView'
import { DonorView } from './views/DonorView'
import { AdminNotifications } from './views/NotificationsView'
import { AdminAnalytics } from './views/AnalyticsView'
import { OutreachView } from './views/OutreachView'

type Role = 'admin' | 'donor'
const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED === 'true'

export default function AdminApp({ user, onSignOut }: { user: AuthUser | null; onSignOut: () => void }) {
  const [role, setRole] = useState<Role>('admin')
  const [view, setView] = useState<AdminView>('overview')
  const [district, setDistrict] = useState('')
  const [language, setLanguage] = useState('en')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [donors, setDonors] = useState<Donor[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [advisory, setAdvisory] = useState<Advisory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [forecastGroup, setForecastGroup] = useState('O-')
  const [donorSearch, setDonorSearch] = useState('')
  const [donorGroup, setDonorGroup] = useState('all')
  const [editingInventory, setEditingInventory] = useState<Inventory | null>(null)
  const [addingDonor, setAddingDonor] = useState(false)
  const [campaignGroup, setCampaignGroup] = useState('O-')
  const [campaignStage, setCampaignStage] = useState(1)
  const [batchSize, setBatchSize] = useState(10)
  const [campaignResult, setCampaignResult] = useState<Campaign | null>(null)
  const [campaignBusy, setCampaignBusy] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!AUTH_REQUIRED && role === 'donor') {
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    Promise.all([
      api.dashboard(district || undefined),
      api.donors(district || undefined),
      api.campaigns(),
    ]).then(([nextDashboard, nextDonors, nextCampaigns]) => {
      if (!active) return
      setDashboard(nextDashboard)
      setDonors(nextDonors)
      setCampaigns(nextCampaigns)
      if (!district && nextDashboard.selected_district) setDistrict(nextDashboard.selected_district)
      setError('')
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Could not reach the RaktSanket API.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [district, refreshKey, role])

  useEffect(() => {
    if (!district || role !== 'admin') return
    let active = true
    api.advisory(district, language)
      .then((value) => { if (active) setAdvisory(value) })
      .catch(() => { if (active) setAdvisory(null) })
    return () => { active = false }
  }, [district, language, refreshKey, role])

  const selectedForecast = dashboard?.forecasts.find((forecast) => forecast.blood_group === forecastGroup)
  const navigation = adminNavigation
  const title = navigation.find((item) => item.id === view)?.label ?? 'Overview'
  const visibleDonors = donors.filter((donor) => {
    const matchesSearch = `${donor.name} ${donor.blood_group}`.toLowerCase().includes(donorSearch.toLowerCase())
    return matchesSearch && (donorGroup === 'all' || donor.blood_group === donorGroup)
  })

  async function reload() {
    setRefreshKey((key) => key + 1)
  }

  async function saveInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingInventory) return
    const form = new FormData(event.currentTarget)
    await api.updateInventory(editingInventory.id, {
      units_available: Number(form.get('units_available')),
      avg_daily_demand: Number(form.get('avg_daily_demand')),
      safety_stock_units: Number(form.get('safety_stock_units')),
    })
    setEditingInventory(null)
    await reload()
  }

  async function saveDonor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    await api.createDonor({
      name: String(form.get('name')),
      district: String(form.get('district')).trim(),
      blood_group: String(form.get('blood_group')),
      age: Number(form.get('age')),
      last_donation_date: String(form.get('last_donation_date')) || null,
      donations_count: Number(form.get('donations_count')),
      response_rate: Number(form.get('response_rate')),
    })
    setAddingDonor(false)
    await reload()
  }

  async function launchCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCampaignBusy(true)
    try {
      const result = await api.createCampaign({ district, blood_group: campaignGroup, stage: campaignStage, batch_size: batchSize })
      setCampaignResult(result)
      await reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not create the campaign.')
    } finally {
      setCampaignBusy(false)
    }
  }

  function openView(nextView: AdminView) {
    setView(nextView)
    setSidebarOpen(false)
  }

  function switchRole(nextRole: Role) {
    if (AUTH_REQUIRED) return
    setRole(nextRole)
    setView('overview')
    setSidebarOpen(false)
  }

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" onClick={(event) => { event.preventDefault(); openView('overview') }}>
          <span className="brand-mark"><Droplet size={21} fill="currentColor" /></span>
          <span className="brand-copy"><strong>RaktSanket</strong><small>Blood operations</small></span>
          <button className="sidebar-close icon-button" aria-label="Close menu" onClick={(event) => { event.preventDefault(); setSidebarOpen(false) }}><X size={17} /></button>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        {!AUTH_REQUIRED ? <div className="role-switch" aria-label="Choose demo role">
          <button className={role === 'admin' ? 'role-active' : ''} onClick={() => switchRole('admin')}><Gauge size={14} />Admin</button>
          <button className={role === 'donor' ? 'role-active' : ''} onClick={() => { setRole('donor'); setSidebarOpen(false) }}><HeartPulse size={14} />Donor</button>
        </div> : <div className="auth-account-label"><ShieldCheck size={14} />Admin console · signed in</div>}
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'nav-active' : ''}`} onClick={() => openView(id)}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
              {id === 'inventory' && dashboard?.totals.at_risk_groups ? <b className="nav-count">{dashboard.totals.at_risk_groups}</b> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-indicator"><span className="connection-dot" /><span>API connected</span><small>DEMO</small></div>
          <div className="profile-row"><span className="profile-avatar">{user?.email.slice(0, 2).toUpperCase() ?? 'RS'}</span><span className="profile-meta"><strong>{user?.email ?? 'District operator'}</strong><small>{user ? `${user.role} account` : 'Amravati blood bank'}</small></span>{AUTH_REQUIRED && <button className="signout-button" onClick={onSignOut}>Sign out</button>}</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>Admin</span><span className="crumb-slash">/</span><strong>{title}</strong></div>
          <div className="topbar-actions">
            <label className="district-select"><MapPin size={15} /><select aria-label="Select district" value={district} onChange={(event) => setDistrict(event.target.value)}>
              {(dashboard?.districts ?? []).length === 0 && <option value="">No districts yet</option>}
              {(dashboard?.districts ?? []).map((name) => <option key={name} value={name}>{name}</option>)}
            </select><ChevronDown size={14} /></label>
            <label className="language-select"><span className="sr-only">Advisory language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">EN</option><option value="hi">HI</option><option value="mr">MR</option></select><ChevronDown size={13} /></label>
            <span className="topbar-divider" />
            <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button>
            {AUTH_REQUIRED ? <button className="operator-avatar operator-signout" aria-label="Sign out" title="Sign out" onClick={onSignOut}>{user?.email.slice(0, 2).toUpperCase()}</button> : <span className="operator-avatar">MK</span>}
          </div>
        </header>

        <div className="page-wrap">
          <div className="page-heading">
            <div><div className="eyebrow"><span className="eyebrow-mark" />{`LIVE DISTRICT VIEW / ${district || 'Loading district'}`}</div><h1>{view === 'overview' ? 'Good morning, operator' : title}</h1><p>{view === 'overview' ? 'Here’s the blood availability picture for your district.' : pageDescription(view)}</p></div>
            <div className="heading-actions"><span className="updated-at"><span className="live-pulse" />Synced just now</span><button className="button button-outline button-compact" onClick={reload} title="Refresh dashboard"><RefreshCw size={15} /><span>Refresh</span></button></div>
          </div>

          {error && <div className="error-banner"><TriangleAlert size={17} /><span><strong>Connection issue.</strong> {error} Start the API at localhost:8000 to load live demo records.</span><button className="icon-button" onClick={() => setError('')} aria-label="Dismiss"><X size={16} /></button></div>}
          {!AUTH_REQUIRED && role === 'donor' ? <DonorPortal donors={donors} fixedDonorId={undefined} onRefresh={reload} /> : loading && !dashboard ? <div className="loading-state"><span className="spinner" /><span>Connecting to district records…</span></div> : dashboard ? <>
            {!AUTH_REQUIRED && <div className="demo-strip"><span className="demo-dot" /><strong>DEMO DATA</strong><span>Generated sample records for interface testing. Replace with approved district data before operational use.</span><button onClick={() => openView('outreach')}>Open outreach <ArrowRight size={14} /></button></div>}
            {dashboard && view === 'overview' && <Overview dashboard={dashboard} advisory={advisory} language={language} setLanguage={setLanguage} forecastGroup={forecastGroup} setForecastGroup={setForecastGroup} selectedForecast={selectedForecast} onGoOutreach={() => openView('outreach')} onSelectStock={(group) => { setForecastGroup(group); openView('inventory') }} onSelectDonor={() => openView('ranking')} />}
            {dashboard && view === 'inventory' && <InventoryView inventory={dashboard.inventory} forecasts={dashboard.forecasts} selectedGroup={forecastGroup} setSelectedGroup={setForecastGroup} onEdit={setEditingInventory} />}
            {dashboard && view === 'forecast' && <ForecastView forecasts={dashboard.forecasts} />}
            {dashboard && (view === 'donors' || view === 'ranking') && <DonorView donors={visibleDonors} search={donorSearch} setSearch={setDonorSearch} bloodGroup={donorGroup} setBloodGroup={setDonorGroup} onAdd={() => setAddingDonor(true)} ranking={view === 'ranking'} />}
            {dashboard && view === 'notifications' && <AdminNotifications campaigns={campaigns} />}
            {dashboard && view === 'analytics' && <AdminAnalytics dashboard={dashboard} campaigns={campaigns} />}
            {dashboard && view === 'outreach' && <OutreachView campaigns={campaigns} district={district} bloodGroup={campaignGroup} setBloodGroup={setCampaignGroup} stage={campaignStage} setStage={setCampaignStage} batchSize={batchSize} setBatchSize={setBatchSize} result={campaignResult} busy={campaignBusy} onSubmit={launchCampaign} />}
          </> : <div className="empty-state"><HeartPulse size={24} /><strong>Dashboard unavailable</strong><span>Check that the RaktSanket API is running and try again.</span><button className="button button-primary" onClick={reload}><RefreshCw size={15} />Retry connection</button></div>}
          <footer className="page-footer"><span>RaktSanket <b>·</b> Pilot operations console</span><span><ShieldCheck size={14} />Human review required before donor contact</span></footer>
        </div>
      </main>

      {editingInventory && <Modal title={`Update ${editingInventory.blood_group} stock`} onClose={() => setEditingInventory(null)}><form className="form-stack" onSubmit={saveInventory}><label>Units available<input name="units_available" type="number" min="0" defaultValue={editingInventory.units_available} required /></label><label>Average daily demand<input name="avg_daily_demand" type="number" min="0.1" step="0.1" defaultValue={editingInventory.avg_daily_demand} required /></label><label>Safety stock threshold<input name="safety_stock_units" type="number" min="0" defaultValue={editingInventory.safety_stock_units} required /></label><div className="modal-actions"><button type="button" className="button button-outline" onClick={() => setEditingInventory(null)}>Cancel</button><button className="button button-primary"><Check size={15} />Save stock</button></div></form></Modal>}
      {addingDonor && <Modal title="Add donor record" onClose={() => setAddingDonor(false)}><form className="form-stack" onSubmit={saveDonor}><label>Full name<input name="name" minLength={2} placeholder="Donor name" required /></label><label>District<input name="district" list="donor-district-options" defaultValue={district} minLength={2} maxLength={80} placeholder="Enter district" required /><datalist id="donor-district-options">{(dashboard?.districts ?? []).map((name) => <option key={name} value={name} />)}</datalist></label><div className="form-row"><label>Blood group<select name="blood_group" defaultValue="O+">{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label><label>Age<input name="age" type="number" min="18" max="65" defaultValue="28" required /></label></div><label>Last donation date<input name="last_donation_date" type="date" /></label><div className="form-row"><label>Previous donations<input name="donations_count" type="number" min="0" defaultValue="1" required /></label><label>Past response rate<input name="response_rate" type="number" min="0" max="1" step="0.05" defaultValue="0.6" required /></label></div><div className="modal-actions"><button type="button" className="button button-outline" onClick={() => setAddingDonor(false)}>Cancel</button><button className="button button-primary"><Plus size={15} />Add donor</button></div></form></Modal>}
    </div>
  )
}
