import { Activity, ArrowDownRight, ArrowRight, ChevronDown, HeartPulse, PackageCheck, Send, TriangleAlert, Users } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Metric, RiskPill, SparkMark, bloodGroups, dateLabel } from '../components/shared'
import type { Advisory, Dashboard, Forecast } from '../../lib/types'

export function Overview({ dashboard, advisory, language, setLanguage, forecastGroup, setForecastGroup, selectedForecast, onGoOutreach, onSelectStock, onSelectDonor }: {
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
