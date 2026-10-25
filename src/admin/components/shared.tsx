import { Activity, BarChart3, Bell, Gauge, LayoutDashboard, PackageCheck, Radio, Users, ArrowDownRight, X } from 'lucide-react'
import type { ReactNode } from 'react'

export type AdminView = 'overview' | 'inventory' | 'forecast' | 'donors' | 'ranking' | 'notifications' | 'analytics' | 'outreach'

export const adminNavigation: { id: AdminView; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'inventory', label: 'Blood Inventory', icon: PackageCheck },
  { id: 'forecast', label: 'Demand Forecast', icon: Activity },
  { id: 'donors', label: 'Donor Management', icon: Users },
  { id: 'ranking', label: 'CBSRI Ranking', icon: Gauge },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'outreach', label: 'Outreach', icon: Radio },
]
export const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

export function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function RiskPill({ level }: { level: string }) {
  return <span className={`risk-pill risk-${level}`}><i />{level}</span>
}

export function SparkMark() {
  return <span className="spark-mark"><Activity size={13} /></span>
}

export function Metric({ label, value, note, icon: Icon, tone }: { label: string; value: string; note: string; icon: typeof Activity; tone: string }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon metric-${tone}`}><Icon size={17} /></span></div><strong className="metric-value">{value}</strong><div className="metric-note"><span className="metric-change"><ArrowDownRight size={13} /></span>{note}</div></article>
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" aria-label="Close" onClick={onClose}><X size={18} /></button></div>{children}</section></div>
}

export function pageDescription(view: AdminView) {
  return {
    overview: 'District-level availability and donor response outlook.',
    inventory: 'Current units, projected cover, and safety stock by blood group.',
    forecast: 'Review projected stock movement and the safety threshold for each blood group.',
    donors: 'Review eligible donors and their fatigue-adjusted activation priority.',
    ranking: 'CBSRI-ranked donor response priority with model explanations.',
    notifications: 'Review staged donor activation records and delivery status.',
    analytics: 'District stock, shortage risk, donor coverage, and outreach activity.',
    outreach: 'Simulate staged contact lists for human review before activation.',
  }[view]
}

