import { useState } from 'react'
import { CalendarDays, Check, CircleX, HeartPulse, MapPin, PackageCheck, ShieldCheck } from 'lucide-react'
import type { AdminBloodRequest, BloodRequestStatus } from '../../lib/types'

type Filter = 'open' | BloodRequestStatus | 'all'
export type ReviewDecision = Exclude<BloodRequestStatus, 'pending review'>

// The decisions each status allows; mirrors REVIEW_TRANSITIONS in backend/app/main.py.
const nextSteps: Partial<Record<BloodRequestStatus, ReviewDecision[]>> = {
  'pending review': ['approved', 'rejected'],
  approved: ['fulfilled', 'rejected'],
}
const filters: { id: Filter; label: string }[] = [
  { id: 'open', label: 'Needs action' },
  { id: 'pending review', label: 'Pending' },
  { id: 'approved', label: 'Approved' },
  { id: 'fulfilled', label: 'Fulfilled' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'all', label: 'All' },
]
const decisionLabel: Record<ReviewDecision, string> = { approved: 'Approve', fulfilled: 'Mark fulfilled', rejected: 'Reject' }

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysUntil(value: string) {
  const due = new Date(`${value}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86_400_000)
}

export function StatusChip({ status }: { status: string }) {
  return <span className={`request-status-chip status-${status.replace(/\s+/g, '-')}`}><i />{status}</span>
}

export function RequestsView({ requests, district: _district, filter, setFilter, onReview }: {
  requests: AdminBloodRequest[]
  district?: string
  filter: Filter
  setFilter: (value: Filter) => void
  onReview: (request: AdminBloodRequest, decision: ReviewDecision) => void
}) {
  const [districtFilter, setDistrictFilter] = useState<string>('all')
  const availableDistricts = Array.from(new Set(requests.map((r) => r.district).filter(Boolean)))

  const visible = requests.filter((request) => {
    const matchesDistrict = districtFilter === 'all' || request.district.toLowerCase() === districtFilter.toLowerCase()
    if (!matchesDistrict) return false
    if (filter === 'all') return true
    if (filter === 'open') return request.status in nextSteps
    return request.status === filter
  })

  const count = (id: Filter) => requests.filter((request) => {
    const matchesDistrict = districtFilter === 'all' || request.district.toLowerCase() === districtFilter.toLowerCase()
    if (!matchesDistrict) return false
    return id === 'all' ? true : id === 'open' ? request.status in nextSteps : request.status === id
  }).length

  return <section className="panel table-panel requests-panel">
    <div className="panel-heading">
      <div>
        <div className="eyebrow">DONOR-SUBMITTED · {districtFilter === 'all' ? 'ALL DISTRICTS' : districtFilter.toUpperCase()}</div>
        <h2>Blood requests</h2>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {availableDistricts.length > 0 && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            <MapPin size={13} />
            <select
              aria-label="Filter by district"
              value={districtFilter}
              onChange={(e) => setDistrictFilter(e.target.value)}
              style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--line)', background: '#fff', fontSize: 12 }}
            >
              <option value="all">All districts ({requests.length})</option>
              {availableDistricts.map((dist) => (
                <option key={dist} value={dist}>{dist} ({requests.filter((r) => r.district.toLowerCase() === dist.toLowerCase()).length})</option>
              ))}
            </select>
          </label>
        )}
        <span className="record-count">{visible.length} shown</span>
      </div>
    </div>
    <div className="request-filters" role="tablist" aria-label="Filter requests by status">
      {filters.map(({ id, label }) => <button key={id} role="tab" aria-selected={filter === id} className={filter === id ? 'request-filter-active' : ''} onClick={() => setFilter(id)}>{label}<small>{count(id)}</small></button>)}
    </div>
    <div className="table-wrap"><table><thead><tr><th>DONOR</th><th>DISTRICT</th><th>GROUP</th><th>UNITS</th><th>HOSPITAL</th><th>NEEDED BY</th><th>SUBMITTED</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>
      {visible.map((request) => {
        const due = daysUntil(request.needed_by)
        const steps = nextSteps[request.status] ?? []
        return <tr key={request.id}>
          <td><span className="donor-cell-name"><strong>{request.donor_name.replace(' (demo)', '')}</strong><small>Donor #{request.donor_id}</small></span></td>
          <td><span className="district-chip"><MapPin size={11} style={{ display: 'inline', verticalAlign: -1, marginRight: 2 }} />{request.district}</span></td>
          <td><span className="blood-type">{request.blood_group}</span></td>
          <td><strong>{request.units_requested}</strong></td>
          <td><span className="donor-cell-name"><strong>{request.hospital_name}</strong>{request.notes && <small className="request-notes" title={request.notes}>{request.notes}</small>}</span></td>
          <td><span className={`due-date ${steps.length && due <= 2 ? 'due-soon' : ''}`}><CalendarDays size={12} />{formatDate(request.needed_by)}</span>{steps.length > 0 && <small className="due-hint">{due < 0 ? `${-due} day${due === -1 ? '' : 's'} overdue` : due === 0 ? 'today' : `in ${due} day${due === 1 ? '' : 's'}`}</small>}</td>
          <td>{formatDate(request.created_at)}</td>
          <td><StatusChip status={request.status} />{request.admin_note && <small className="request-admin-note" title={request.admin_note}>{request.admin_note}</small>}</td>
          <td><div className="request-actions">{steps.length ? steps.map((decision) => <button key={decision} className={`button button-compact ${decision === 'rejected' ? 'button-outline' : 'button-primary'}`} onClick={() => onReview(request, decision)}>{decision === 'rejected' ? <CircleX size={14} /> : decision === 'fulfilled' ? <PackageCheck size={14} /> : <Check size={14} />}<span>{decisionLabel[decision]}</span></button>) : <span className="request-closed">Closed{request.reviewed_at ? ` · ${formatDate(request.reviewed_at)}` : ''}</span>}</div></td>
        </tr>
      })}
    </tbody></table>
    {visible.length === 0 && <div className="table-empty"><HeartPulse size={18} />{requests.length ? 'No requests match the selected filters.' : 'No blood requests from donors yet.'}</div>}</div>
    <div className="table-endnote"><ShieldCheck size={14} />Approving records the decision for the donor to see. Arrange the issue of blood through the blood bank's own process.</div>
  </section>
}

export type { Filter as RequestFilter }
