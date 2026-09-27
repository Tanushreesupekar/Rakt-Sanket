import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity, ArrowDownRight, ArrowRight, BarChart3, Bell, Check, ChevronDown, Clock3, Droplet,
  HeartPulse, LayoutDashboard, MapPin, Menu, PackageCheck, Plus, Radio, RefreshCw,
  Search, Send, ShieldCheck, SlidersHorizontal, TriangleAlert, Users, X, Gauge,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from './api'
import { clearSession, getSessionUser, hasSessionToken } from './api'
import AuthGate from './AuthGate'
import DonorPortal from './DonorPortal'
import type { Advisory, AuthUser, Campaign, Dashboard, Donor, Forecast, Inventory } from './types'

type Role = 'admin' | 'donor'
type View = 'overview' | 'inventory' | 'forecast' | 'donors' | 'ranking' | 'notifications' | 'analytics' | 'outreach' | 'donor'

const adminNavigation: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'inventory', label: 'Blood Inventory', icon: PackageCheck },
  { id: 'forecast', label: 'Demand Forecast', icon: Activity },
  { id: 'donors', label: 'Donor Management', icon: Users },
  { id: 'ranking', label: 'CBSRI Ranking', icon: Gauge },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'outreach', label: 'Outreach', icon: Radio },
]
const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED === 'true'

function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function RiskPill({ level }: { level: string }) {
  return <span className={`risk-pill risk-${level}`}><i />{level}</span>
}

function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => AUTH_REQUIRED ? getSessionUser() : null)
  const [sessionReady, setSessionReady] = useState(!AUTH_REQUIRED)
  const [role, setRole] = useState<Role>(() => AUTH_REQUIRED && getSessionUser()?.role === 'donor' ? 'donor' : 'admin')
  const [view, setView] = useState<View>(() => AUTH_REQUIRED && getSessionUser()?.role === 'donor' ? 'donor' : 'overview')
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
      setRole(user.role)
      setView(user.role === 'donor' ? 'donor' : 'overview')
    }).catch(() => {
      clearSession()
      if (active) setAuthUser(null)
    }).finally(() => { if (active) setSessionReady(true) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!sessionReady || (AUTH_REQUIRED && !authUser) || role === 'donor') {
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
  }, [district, refreshKey, role, authUser, sessionReady])

  useEffect(() => {
    if (!district || (AUTH_REQUIRED && !authUser) || role !== 'admin') return
    let active = true
    api.advisory(district, language)
      .then((value) => { if (active) setAdvisory(value) })
      .catch(() => { if (active) setAdvisory(null) })
    return () => { active = false }
  }, [district, language, refreshKey, role, authUser])

  const selectedForecast = dashboard?.forecasts.find((forecast) => forecast.blood_group === forecastGroup)
  const navigation = role === 'admin' ? adminNavigation : [{ id: 'donor' as const, label: 'Donor Portal', icon: HeartPulse }]
  const title = navigation.find((item) => item.id === view)?.label ?? 'Donor Portal'
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

  function openView(nextView: View) {
    setView(nextView)
    setSidebarOpen(false)
  }

  function switchRole(nextRole: Role) {
    if (AUTH_REQUIRED) return
    setRole(nextRole)
    setView(nextRole === 'admin' ? 'overview' : 'donor')
    setSidebarOpen(false)
  }

  function signOut() {
    clearSession()
    setAuthUser(null)
    setRole('admin')
    setView('overview')
    setDashboard(null)
    setDonors([])
    setCampaigns([])
  }

  if (AUTH_REQUIRED && !sessionReady) return <div className="auth-loading"><span className="spinner" />Verifying session…</div>
  if (AUTH_REQUIRED && !authUser) return <AuthGate onAuthenticated={(user) => {
    setAuthUser(user)
    setRole(user.role)
    setView(user.role === 'donor' ? 'donor' : 'overview')
  }} />

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
          <button className={role === 'donor' ? 'role-active' : ''} onClick={() => switchRole('donor')}><HeartPulse size={14} />Donor</button>
        </div> : <div className="auth-account-label"><ShieldCheck size={14} />Signed-in account</div>}
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'nav-active' : ''}`} onClick={() => openView(id)}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
              {role === 'admin' && id === 'inventory' && dashboard?.totals.at_risk_groups ? <b className="nav-count">{dashboard.totals.at_risk_groups}</b> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-indicator"><span className="connection-dot" /><span>API connected</span><small>DEMO</small></div>
          <div className="profile-row"><span className="profile-avatar">{authUser?.email.slice(0, 2).toUpperCase() ?? 'RS'}</span><span className="profile-meta"><strong>{authUser?.email ?? 'District operator'}</strong><small>{authUser ? `${authUser.role} account` : 'Amravati blood bank'}</small></span>{AUTH_REQUIRED && <button className="signout-button" onClick={signOut}>Sign out</button>}</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>{role === 'admin' ? 'Admin' : 'Donor'}</span><span className="crumb-slash">/</span><strong>{title}</strong></div>
          <div className="topbar-actions">
            {role === 'admin' && <label className="district-select"><MapPin size={15} /><select aria-label="Select district" value={district} onChange={(event) => setDistrict(event.target.value)}>
              {(dashboard?.districts ?? []).length === 0 && <option value="">No districts yet</option>}
              {(dashboard?.districts ?? []).map((name) => <option key={name} value={name}>{name}</option>)}
            </select><ChevronDown size={14} /></label>}
            {role === 'admin' && <label className="language-select"><span className="sr-only">Advisory language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">EN</option><option value="hi">HI</option><option value="mr">MR</option></select><ChevronDown size={13} /></label>}
            <span className="topbar-divider" />
            <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button>
            {AUTH_REQUIRED ? <button className="operator-avatar operator-signout" aria-label="Sign out" title="Sign out" onClick={signOut}>{authUser?.email.slice(0, 2).toUpperCase()}</button> : <span className="operator-avatar">MK</span>}
          </div>
        </header>

        <div className="page-wrap">
          <div className="page-heading">
            <div><div className="eyebrow"><span className="eyebrow-mark" />{role === 'admin' ? `LIVE DISTRICT VIEW / ${district || 'Loading district'}` : `DONOR ACCESS / ${AUTH_REQUIRED ? 'SIGNED-IN ACCOUNT' : 'DEMO ACCOUNT'}`}</div><h1>{role === 'admin' && view === 'overview' ? 'Good morning, operator' : role === 'donor' ? 'Welcome to your donor space' : title}</h1><p>{role === 'admin' && view === 'overview' ? 'Here’s the blood availability picture for your district.' : pageDescription(view)}</p></div>
            <div className="heading-actions"><span className="updated-at"><span className="live-pulse" />Synced just now</span><button className="button button-outline button-compact" onClick={reload} title="Refresh dashboard"><RefreshCw size={15} /><span>Refresh</span></button></div>
          </div>

          {error && <div className="error-banner"><TriangleAlert size={17} /><span><strong>Connection issue.</strong> {error} Start the API at localhost:8000 to load live demo records.</span><button className="icon-button" onClick={() => setError('')} aria-label="Dismiss"><X size={16} /></button></div>}
          {role === 'donor' ? <DonorPortal donors={donors} fixedDonorId={AUTH_REQUIRED ? authUser?.donor_id : undefined} onRefresh={reload} /> : loading && !dashboard ? <div className="loading-state"><span className="spinner" /><span>Connecting to district records…</span></div> : dashboard ? <>
            {!AUTH_REQUIRED && <div className="demo-strip"><span className="demo-dot" /><strong>DEMO DATA</strong><span>{role === 'admin' ? 'Generated sample records for interface testing. Replace with approved district data before operational use.' : 'Role switching and donor identity are demonstrations; no account authentication is configured.'}</span>{role === 'admin' && <button onClick={() => openView('outreach')}>Open outreach <ArrowRight size={14} /></button>}</div>}
            {role === 'admin' && dashboard && view === 'overview' && <Overview dashboard={dashboard} advisory={advisory} language={language} setLanguage={setLanguage} forecastGroup={forecastGroup} setForecastGroup={setForecastGroup} selectedForecast={selectedForecast} onGoOutreach={() => openView('outreach')} onSelectStock={(group) => { setForecastGroup(group); openView('inventory') }} onSelectDonor={() => openView('ranking')} />}
            {role === 'admin' && dashboard && view === 'inventory' && <InventoryView inventory={dashboard.inventory} forecasts={dashboard.forecasts} selectedGroup={forecastGroup} setSelectedGroup={setForecastGroup} onEdit={setEditingInventory} />}
            {role === 'admin' && dashboard && view === 'forecast' && <ForecastView forecasts={dashboard.forecasts} />}
            {role === 'admin' && dashboard && (view === 'donors' || view === 'ranking') && <DonorView donors={visibleDonors} search={donorSearch} setSearch={setDonorSearch} bloodGroup={donorGroup} setBloodGroup={setDonorGroup} onAdd={() => setAddingDonor(true)} ranking={view === 'ranking'} />}
            {role === 'admin' && dashboard && view === 'notifications' && <AdminNotifications campaigns={campaigns} />}
            {role === 'admin' && dashboard && view === 'analytics' && <AdminAnalytics dashboard={dashboard} campaigns={campaigns} />}
            {role === 'admin' && dashboard && view === 'outreach' && <OutreachView campaigns={campaigns} district={district} bloodGroup={campaignGroup} setBloodGroup={setCampaignGroup} stage={campaignStage} setStage={setCampaignStage} batchSize={batchSize} setBatchSize={setBatchSize} result={campaignResult} busy={campaignBusy} onSubmit={launchCampaign} />}
          </> : <div className="empty-state"><HeartPulse size={24} /><strong>Dashboard unavailable</strong><span>Check that the RaktSanket API is running and try again.</span><button className="button button-primary" onClick={reload}><RefreshCw size={15} />Retry connection</button></div>}
          <footer className="page-footer"><span>RaktSanket <b>·</b> Pilot operations console</span><span><ShieldCheck size={14} />Human review required before donor contact</span></footer>
        </div>
      </main>

      {editingInventory && <Modal title={`Update ${editingInventory.blood_group} stock`} onClose={() => setEditingInventory(null)}><form className="form-stack" onSubmit={saveInventory}><label>Units available<input name="units_available" type="number" min="0" defaultValue={editingInventory.units_available} required /></label><label>Average daily demand<input name="avg_daily_demand" type="number" min="0.1" step="0.1" defaultValue={editingInventory.avg_daily_demand} required /></label><label>Safety stock threshold<input name="safety_stock_units" type="number" min="0" defaultValue={editingInventory.safety_stock_units} required /></label><div className="modal-actions"><button type="button" className="button button-outline" onClick={() => setEditingInventory(null)}>Cancel</button><button className="button button-primary"><Check size={15} />Save stock</button></div></form></Modal>}
      {addingDonor && <Modal title="Add donor record" onClose={() => setAddingDonor(false)}><form className="form-stack" onSubmit={saveDonor}><label>Full name<input name="name" minLength={2} placeholder="Donor name" required /></label><label>District<input name="district" list="donor-district-options" defaultValue={district} minLength={2} maxLength={80} placeholder="Enter district" required /><datalist id="donor-district-options">{(dashboard?.districts ?? []).map((name) => <option key={name} value={name} />)}</datalist></label><div className="form-row"><label>Blood group<select name="blood_group" defaultValue="O+">{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label><label>Age<input name="age" type="number" min="18" max="65" defaultValue="28" required /></label></div><label>Last donation date<input name="last_donation_date" type="date" /></label><div className="form-row"><label>Previous donations<input name="donations_count" type="number" min="0" defaultValue="1" required /></label><label>Past response rate<input name="response_rate" type="number" min="0" max="1" step="0.05" defaultValue="0.6" required /></label></div><div className="modal-actions"><button type="button" className="button button-outline" onClick={() => setAddingDonor(false)}>Cancel</button><button className="button button-primary"><Plus size={15} />Add donor</button></div></form></Modal>}
    </div>
  )
}

function pageDescription(view: View) {
  return {
    overview: 'District-level availability and donor response outlook.',
    inventory: 'Current units, projected cover, and safety stock by blood group.',
    forecast: 'Review projected stock movement and the safety threshold for each blood group.',
    donors: 'Review eligible donors and their fatigue-adjusted activation priority.',
    ranking: 'CBSRI-ranked donor response priority with model explanations.',
    notifications: 'Review staged donor activation records and delivery status.',
    analytics: 'District stock, shortage risk, donor coverage, and outreach activity.',
    outreach: 'Simulate staged contact lists for human review before activation.',
    donor: 'Manage donor availability, blood requests, notifications, and donation history.',
  }[view]
}

function Overview({ dashboard, advisory, language, setLanguage, forecastGroup, setForecastGroup, selectedForecast, onGoOutreach, onSelectStock, onSelectDonor }: {
  dashboard: Dashboard; advisory: Advisory | null; language: string; setLanguage: (value: string) => void
  forecastGroup: string; setForecastGroup: (value: string) => void; selectedForecast?: Forecast
  onGoOutreach: () => void; onSelectStock: (group: string) => void; onSelectDonor: () => void
}) {
  const { totals } = dashboard
  return <>
    <section className="metric-grid" aria-label="District summary">
      <Metric label="Units in stock" value={totals.inventory_units.toLocaleString('en-IN')} note="Across 8 blood groups" icon={PackageCheck} tone="green" />
      <Metric label="Groups at risk" value={String(totals.at_risk_groups).padStart(2, '0')} note={`${totals.critical_groups} critical · 14-day window`} icon={TriangleAlert} tone={totals.critical_groups ? 'coral' : 'gold'} />
      <Metric label="Eligible donors" value={totals.eligible_donors.toLocaleString('en-IN')} note={`of ${totals.donor_count} in this district`} icon={Users} tone="blue" />
      <Metric label="CBSRI · highest" value={`${Math.max(0, ...dashboard.inventory.map((item) => item.cbsri)).toFixed(0)}`} note="Composite response index / 100" icon={Activity} tone="ink" />
    </section>

    <section className="overview-grid">
      <article className="panel forecast-panel">
        <div className="panel-heading"><div><div className="eyebrow">PREDICTIVE OUTLOOK <span className="forecast-horizon">NEXT 14 DAYS</span></div><h2>Stock trajectory</h2></div><label className="inline-select"><span className="sr-only">Blood group for forecast</span><select value={forecastGroup} onChange={(event) => setForecastGroup(event.target.value)}>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select><ChevronDown size={14} /></label></div>
        {selectedForecast ? <>
          <div className="chart-summary"><strong>{selectedForecast.current_units} <small>units now</small></strong><span><ArrowDownRight size={15} />{selectedForecast.avg_daily_demand.toFixed(1)} units avg. daily demand</span><RiskPill level={selectedForecast.points.at(-1)?.risk_level ?? 'stable'} /></div>
          <div className="forecast-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={selectedForecast.points} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}><defs><linearGradient id="stockFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#33876a" stopOpacity={0.24} /><stop offset="100%" stopColor="#33876a" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid stroke="#e7ece8" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickFormatter={dateLabel} tickLine={false} axisLine={false} tick={{ fill: '#87928b', fontSize: 11 }} minTickGap={26} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#87928b', fontSize: 11 }} width={42} /><Tooltip labelFormatter={(label) => dateLabel(String(label))} formatter={(value, name) => [`${value} units`, name === 'projected_units' ? 'Projected stock' : 'Safety stock']} contentStyle={{ border: '1px solid #dfe6e0', borderRadius: 7, fontSize: 12 }} /><ReferenceLine y={selectedForecast.safety_stock_units} stroke="#db8c58" strokeDasharray="5 4" label={{ value: 'Safety stock', fill: '#b77b4c', fontSize: 10, position: 'insideTopRight' }} /><Area type="monotone" dataKey="projected_units" name="Projected stock" stroke="#27765a" strokeWidth={2.5} fill="url(#stockFill)" activeDot={{ r: 4, fill: '#27765a', stroke: '#fff', strokeWidth: 2 }} /></AreaChart></ResponsiveContainer></div>
          <div className="chart-footnote"><span><i className="legend-stock" />Projected units</span><span><i className="legend-safety" />Safety stock threshold</span><span className="chart-cbsri">CBSRI <strong>{selectedForecast.cbsri.toFixed(1)}</strong></span></div>
        </> : <div className="chart-empty">Forecast not available for this blood group.</div>}
      </article>

      <article className="advisory-panel">
        <div className="advisory-topline"><span><SparkMark />FIELD ADVISORY</span><span className="advisory-score">CBSRI <b>{advisory?.cbsri.toFixed(0) ?? '—'}</b></span></div>
        <div className="advisory-body"><span className="advisory-icon"><HeartPulse size={20} /></span><RiskPill level={advisory?.cbsri !== undefined ? advisory.cbsri >= 70 ? 'critical' : advisory.cbsri >= 45 ? 'elevated' : 'stable' : 'stable'} /><h2>{advisory?.title ?? 'Advisory loading'}</h2><p>{advisory?.message ?? 'Calculating the latest district outlook.'}</p></div>
        <div className="advisory-action"><span className="action-label">RECOMMENDED NEXT STEP</span><p>{advisory?.action ?? 'Review available stock and donor readiness.'}</p><button className="button button-primary" onClick={onGoOutreach}><Send size={15} />Review outreach tiers</button></div>
        <div className="advisory-language"><span>Advisory language</span><label><select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="mr">मराठी</option></select><ChevronDown size={13} /></label></div>
      </article>
    </section>

    <section className="lower-grid">
      <article className="panel stock-panel"><div className="panel-heading compact-heading"><div><div className="eyebrow">LIVE INVENTORY</div><h2>Blood group watch</h2></div><button className="text-link" onClick={() => onSelectStock(dashboard.inventory.slice().sort((a, b) => b.cbsri - a.cbsri)[0]?.blood_group ?? 'O-')}>View stock <ArrowRight size={14} /></button></div><div className="stock-list">{dashboard.inventory.slice().sort((a, b) => b.cbsri - a.cbsri).slice(0, 5).map((item) => <button className="stock-row" key={item.id} onClick={() => onSelectStock(item.blood_group)}><span className="blood-type">{item.blood_group}</span><span className="stock-main"><span className="stock-name">{item.units_available} units <small>· {item.days_of_supply} days cover</small></span><span className="stock-meter"><i style={{ width: `${Math.min(100, item.units_available / Math.max(1, item.safety_stock_units) * 100)}%` }} /></span></span><span className="stock-score">{item.cbsri.toFixed(0)}<small> CBSRI</small></span><RiskPill level={item.risk_level} /></button>)}</div></article>
      <article className="panel donor-panel"><div className="panel-heading compact-heading"><div><div className="eyebrow">RESPONSE PRIORITY</div><h2>Ready to contact</h2></div><button className="text-link" onClick={onSelectDonor}>All donors <ArrowRight size={14} /></button></div><div className="mini-donor-list">{dashboard.top_donors.slice(0, 4).map((donor, index) => <div className="mini-donor" key={donor.id}><span className={`donor-avatar donor-avatar-${index % 4}`}>{donor.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><span className="mini-donor-name"><strong>{donor.name.replace(' (demo)', '')}</strong><small>{donor.blood_group} <i /> {Math.round(donor.response_probability * 100)}% response</small></span><span className="priority-score">{donor.priority_score.toFixed(0)}<small>PRIORITY</small></span></div>)}</div></article>
    </section>
  </>
}

function SparkMark() {
  return <span className="spark-mark"><Activity size={13} /></span>
}

function Metric({ label, value, note, icon: Icon, tone }: { label: string; value: string; note: string; icon: typeof Activity; tone: string }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon metric-${tone}`}><Icon size={17} /></span></div><strong className="metric-value">{value}</strong><div className="metric-note"><span className="metric-change"><ArrowDownRight size={13} /></span>{note}</div></article>
}

function InventoryView({ inventory, forecasts, selectedGroup, setSelectedGroup, onEdit }: { inventory: Inventory[]; forecasts: Forecast[]; selectedGroup: string; setSelectedGroup: (group: string) => void; onEdit: (item: Inventory) => void }) {
  const forecast = forecasts.find((item) => item.blood_group === selectedGroup)
  const sorted = inventory.slice().sort((a, b) => b.cbsri - a.cbsri)
  return <div className="work-grid">
    <section className="panel table-panel"><div className="panel-heading"><div><div className="eyebrow">CURRENT UNITS · {inventory[0]?.district.toUpperCase()}</div><h2>Inventory by blood group</h2></div><span className="record-count">{inventory.length} records</span></div><div className="table-wrap"><table><thead><tr><th>GROUP</th><th>AVAILABLE</th><th>DAILY NEED</th><th>DAYS COVER</th><th>OUTLOOK</th><th>CBSRI</th><th /></tr></thead><tbody>{sorted.map((item) => <tr key={item.id} className={selectedGroup === item.blood_group ? 'row-selected' : ''} onClick={() => setSelectedGroup(item.blood_group)}><td><span className="blood-type">{item.blood_group}</span></td><td><strong>{item.units_available}</strong><span className="cell-unit"> units</span></td><td>{item.avg_daily_demand.toFixed(1)} units</td><td><span className={item.days_of_supply < 7 ? 'days-low' : ''}>{item.days_of_supply.toFixed(1)} days</span></td><td><RiskPill level={item.risk_level} /></td><td><strong className="cbsri-cell">{item.cbsri.toFixed(1)}</strong></td><td><button className="icon-button edit-button" title={`Edit ${item.blood_group} stock`} aria-label={`Edit ${item.blood_group} stock`} onClick={(event) => { event.stopPropagation(); onEdit(item) }}><SlidersHorizontal size={16} /></button></td></tr>)}</tbody></table></div></section>
    {forecast && <section className="panel forecast-detail"><div className="panel-heading"><div><div className="eyebrow">{forecast.horizon_days}-DAY PROJECTION</div><h2>{forecast.blood_group} outlook</h2></div><RiskPill level={forecast.points.at(-1)?.risk_level ?? 'stable'} /></div><div className="forecast-detail-stats"><div><span>Current units</span><strong>{forecast.current_units}</strong></div><div><span>Safety level</span><strong>{forecast.safety_stock_units}</strong></div><div><span>Response index</span><strong>{forecast.cbsri.toFixed(1)}</strong></div></div><p className="explanation-block"><SparkMark />{forecast.explanation}</p><div className="detail-timeline">{forecast.points.filter((_, index) => index % 3 === 0 || index === forecast.points.length - 1).map((point) => <div className="timeline-point" key={point.date}><span className="timeline-date">{dateLabel(point.date)}</span><span className="timeline-line"><i style={{ height: `${Math.max(10, point.projected_units / Math.max(1, forecast.current_units) * 100)}%` }} /></span><strong>{point.projected_units}</strong></div>)}</div><button className="button button-outline full-button" onClick={() => onEdit(inventory.find((item) => item.blood_group === forecast.blood_group)!)}><SlidersHorizontal size={15} />Adjust inventory inputs</button></section>}
  </div>
}

function ForecastView({ forecasts }: { forecasts: Forecast[] }) {
  const ordered = forecasts.slice().sort((a, b) => b.cbsri - a.cbsri)
  return <section className="panel forecast-board"><div className="panel-heading"><div><div className="eyebrow">7–14 DAY DEMAND OUTLOOK</div><h2>Forecast by blood group</h2></div><span className="record-count">{forecasts.length} blood groups</span></div><div className="forecast-board-grid">{ordered.map((forecast) => {
    const finalPoint = forecast.points.at(-1)
    const maxUnits = Math.max(forecast.current_units, 1)
    return <article className="forecast-group-card" key={forecast.blood_group}><div className="forecast-group-heading"><span className="blood-type">{forecast.blood_group}</span><RiskPill level={finalPoint?.risk_level ?? 'stable'} /><span className="forecast-cbsri">{forecast.cbsri.toFixed(0)}<small> CBSRI</small></span></div><div className="forecast-bar-chart">{forecast.points.filter((_, index) => index % 2 === 0 || index === forecast.points.length - 1).map((point) => <span className="forecast-bar" key={point.date} title={`${dateLabel(point.date)}: ${point.projected_units} units`}><i className={point.projected_units < forecast.safety_stock_units ? 'bar-under-safety' : ''} style={{ height: `${Math.max(4, point.projected_units / maxUnits * 100)}%` }} /></span>)}</div><div className="forecast-range"><span>{forecast.current_units} units now</span><strong>{finalPoint?.projected_units ?? 0} projected</strong></div><p>{forecast.explanation}</p></article>
  })}</div><p className="request-disclaimer">Pilot forecast uses a weekday-adjusted demand baseline. Validate against local historical stock data before operational use.</p></section>
}

function AdminNotifications({ campaigns }: { campaigns: Campaign[] }) {
  const recipientCount = campaigns.reduce((sum, campaign) => sum + campaign.recipients_count, 0)
  return <div className="admin-notifications-grid"><article className="panel notification-summary"><div className="eyebrow">OUTREACH MONITOR</div><h2>Activation notifications</h2><p>Campaign contact lists and simulation status for the district.</p><div className="notification-summary-stats"><div><strong>{campaigns.length}</strong><span>Rounds prepared</span></div><div><strong>{recipientCount}</strong><span>Donors listed</span></div><div><strong>Simulated</strong><span>Delivery mode</span></div></div><div className="notification-warning"><ShieldCheck size={16} /><span>No messages are sent. Review donor consent and connect an approved provider before real delivery.</span></div></article><article className="panel campaign-history"><div className="panel-heading"><div><div className="eyebrow">RECENT ACTIVITY</div><h2>Campaign log</h2></div><span className="record-count">{campaigns.length} rounds</span></div>{campaigns.length ? campaigns.map((campaign) => <div className="activity-item" key={campaign.id}><span className="activity-mark"><Bell size={15} /></span><div className="activity-content"><strong>Tier {campaign.stage} · {campaign.blood_group} · {campaign.district}</strong><span>{campaign.recipients_count} donor records · CBSRI {campaign.cbsri.toFixed(1)}</span><small>{campaign.donor_names.slice(0, 4).map((name) => name.replace(' (demo)', '')).join(', ') || 'No eligible recipients'}</small></div><span className="request-status">{campaign.status}</span></div>) : <div className="donor-empty"><Bell size={19} /><span>No campaign notifications yet.</span></div>}</article></div>
}

function AdminAnalytics({ dashboard, campaigns }: { dashboard: Dashboard; campaigns: Campaign[] }) {
  const stockCover = dashboard.inventory.reduce((sum, item) => sum + item.days_of_supply, 0) / Math.max(1, dashboard.inventory.length)
  const averageCbsri = dashboard.inventory.reduce((sum, item) => sum + item.cbsri, 0) / Math.max(1, dashboard.inventory.length)
  const sorted = dashboard.inventory.slice().sort((a, b) => b.cbsri - a.cbsri)
  return <div className="analytics-view"><section className="metric-grid"><Metric label="Average days of cover" value={stockCover.toFixed(1)} note="Across tracked blood groups" icon={Clock3} tone="green" /><Metric label="Mean CBSRI" value={averageCbsri.toFixed(1)} note="Composite risk response index" icon={Gauge} tone="ink" /><Metric label="Donor coverage" value={`${dashboard.totals.eligible_donors}/${dashboard.totals.donor_count}`} note="Currently eligible in district" icon={Users} tone="blue" /><Metric label="Campaign rounds" value={String(campaigns.length)} note="Recorded simulated outreach" icon={Radio} tone="gold" /></section><section className="panel analytics-table"><div className="panel-heading"><div><div className="eyebrow">BLOOD GROUP COMPARISON</div><h2>District performance signals</h2></div><BarChart3 size={19} className="donor-panel-icon" /></div><div className="analytics-bars">{sorted.map((item) => <div className="analytics-bar-row" key={item.id}><span className="blood-type">{item.blood_group}</span><span className="analytics-bar-track"><i style={{ width: `${item.cbsri}%` }} /></span><strong>{item.cbsri.toFixed(1)}</strong><RiskPill level={item.risk_level} /><span className="analytics-units">{item.units_available} units · {item.days_of_supply.toFixed(1)} days</span></div>)}</div><p className="request-disclaimer">Signals use synthetic demo stock data and the current pilot scoring weights.</p></section></div>
}

function DonorView({ donors, search, setSearch, bloodGroup, setBloodGroup, onAdd, ranking = false }: { donors: Donor[]; search: string; setSearch: (value: string) => void; bloodGroup: string; setBloodGroup: (value: string) => void; onAdd: () => void; ranking?: boolean }) {
  return <section className="panel table-panel donor-table-panel"><div className="panel-heading"><div><div className="eyebrow">{ranking ? 'CBSRI RESPONSE PRIORITY · MODEL EXPLANATIONS' : 'DONOR RECORDS · ELIGIBILITY & AVAILABILITY'}</div><h2>{ranking ? 'Donor priority ranking' : 'Donor management'}</h2></div>{!ranking && <button className="button button-primary" onClick={onAdd}><Plus size={16} />Add donor</button>}</div><div className="table-toolbar"><label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by name or blood group" /></label><label className="filter-select"><SlidersHorizontal size={15} /><select value={bloodGroup} onChange={(event) => setBloodGroup(event.target.value)}><option value="all">All blood groups</option>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select><ChevronDown size={14} /></label><span className="record-count">{donors.length} donors</span></div><div className="table-wrap"><table><thead><tr>{ranking && <th>RANK</th>}<th>DONOR</th><th>GROUP</th><th>LAST DONATION</th><th>RESPONSE</th><th>CONTACTS · 30D</th><th>PRIORITY</th><th>ELIGIBILITY</th></tr></thead><tbody>{donors.map((donor, index) => <tr key={donor.id}>{ranking && <td><strong className="rank-number">{String(index + 1).padStart(2, '0')}</strong></td>}<td><span className={`table-donor-avatar donor-avatar-${index % 4}`}>{donor.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><span className="donor-cell-name"><strong>{donor.name.replace(' (demo)', '')}</strong><small>{donor.district} · {donor.age} yrs</small></span></td><td><span className="blood-type">{donor.blood_group}</span></td><td>{donor.last_donation_date ? dateLabel(donor.last_donation_date) : 'No record'}</td><td><span className="response-value">{Math.round(donor.response_probability * 100)}%</span><span className="response-track"><i style={{ width: `${donor.response_probability * 100}%` }} /></span></td><td><span className={donor.notifications_30d >= 3 ? 'contacts-high' : ''}>{donor.notifications_30d}</span></td><td><span className="priority-cell">{donor.priority_score.toFixed(1)}</span>{ranking && <span className="rank-explanation" title={donor.explanation}>Why?</span>}</td><td>{donor.eligible ? <span className="eligibility yes"><Check size={13} />Eligible</span> : <span className="eligibility no"><Clock3 size={13} />Hold</span>}</td></tr>)}</tbody></table>{donors.length === 0 && <div className="table-empty">No matching donor records.</div>}</div><div className="table-endnote"><ShieldCheck size={14} />Donor readiness is advisory only. Confirm consent and eligibility before any contact.</div></section>
}

function OutreachView({ campaigns, district, bloodGroup, setBloodGroup, stage, setStage, batchSize, setBatchSize, result, busy, onSubmit }: { campaigns: Campaign[]; district: string; bloodGroup: string; setBloodGroup: (value: string) => void; stage: number; setStage: (value: number) => void; batchSize: number; setBatchSize: (value: number) => void; result: Campaign | null; busy: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <div className="outreach-grid"><section className="panel campaign-panel"><div className="eyebrow">STAGED DONOR ACTIVATION</div><h2>Prepare an outreach round</h2><p className="panel-intro">A prioritized contact list is generated for review. No messages are sent from this demo.</p><form className="campaign-form" onSubmit={onSubmit}><label>Blood group<select value={bloodGroup} onChange={(event) => setBloodGroup(event.target.value)}>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label><div className="campaign-stage-label"><span>Activation tier</span><span>District · {district}</span></div><div className="stage-selector">{[1, 2, 3].map((number) => <button type="button" key={number} className={`stage-option ${stage === number ? 'stage-active' : ''}`} onClick={() => setStage(number)}><span className="stage-number">0{number}</span><strong>{['Priority', 'Expanded', 'Wider'][number - 1]}</strong><small>{['Top ranked donors', 'Next eligible group', 'Remaining candidates'][number - 1]}</small></button>)}</div><label>Donors in this batch<input type="number" min="1" max="100" value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} /></label><button className="button button-primary full-button" disabled={busy}>{busy ? <><span className="button-spinner" />Preparing list…</> : <><Send size={16} />Generate contact list</>}</button><div className="consent-note"><ShieldCheck size={15} /><span>Simulated only. Review consent, donation interval, and local eligibility before contact.</span></div></form></section><section className="panel campaign-history"><div className="panel-heading"><div><div className="eyebrow">ACTIVITY LOG</div><h2>Recent rounds</h2></div><span className="record-count">{campaigns.length} saved</span></div>{result && <div className="campaign-result"><div className="result-mark"><Check size={17} /></div><div><strong>Tier {result.stage} list prepared</strong><span>{result.recipients_count} donors · {result.blood_group} · CBSRI {result.cbsri.toFixed(1)}</span>{result.donor_names.length > 0 && <small>{result.donor_names.join(' · ')}</small>}</div></div>}<div className="activity-list">{campaigns.length ? campaigns.map((campaign) => <div className="activity-item" key={campaign.id}><span className="activity-mark"><Radio size={15} /></span><div className="activity-content"><strong>Tier {campaign.stage} · {campaign.blood_group} activation</strong><span>{campaign.recipients_count} donor records · {campaign.district}</span><small>{campaign.donor_names.slice(0, 3).map((name) => name.replace(' (demo)', '')).join(', ') || 'No eligible donors in this tier'}</small></div><time>{new Date(campaign.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</time></div>) : <div className="history-empty"><Clock3 size={19} /><span>No outreach rounds recorded yet.</span></div>}</div><div className="history-footnote"><TriangleAlert size={14} />Simulated activity only. Connect an approved messaging provider for delivery.</div></section></div>
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" aria-label="Close" onClick={onClose}><X size={18} /></button></div>{children}</section></div>
}

export default App
