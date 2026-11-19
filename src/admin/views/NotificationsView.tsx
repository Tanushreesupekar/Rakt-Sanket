import { Bell, ShieldCheck } from 'lucide-react'
import type { Campaign } from '../../lib/types'

export function AdminNotifications({ campaigns, emailConfigured }: { campaigns: Campaign[]; emailConfigured: boolean }) {
  const recipientCount = campaigns.reduce((sum, campaign) => sum + campaign.recipients_count, 0)
  const emailedCount = campaigns.reduce((sum, campaign) => sum + campaign.emailed_count, 0)
  return <div className="admin-notifications-grid">
    <article className="panel notification-summary">
      <div className="eyebrow">OUTREACH MONITOR</div>
      <h2>Activation notifications</h2>
      <p>Campaign contact lists and email delivery status for the district.</p>
      <div className="notification-summary-stats">
        <div><strong>{campaigns.length}</strong><span>Rounds prepared</span></div>
        <div><strong>{recipientCount}</strong><span>Donors listed</span></div>
        <div><strong>{emailConfigured ? emailedCount : 'Simulated'}</strong><span>{emailConfigured ? 'Emails delivered' : 'Delivery mode'}</span></div>
      </div>
      <div className="notification-warning"><ShieldCheck size={16} /><span>{emailConfigured ? 'Email goes only to donors with a linked, active login. Review consent and delivery outcomes before operational use.' : 'SMTP is not configured, so no email is sent. Add SMTP settings and a linked donor login to deliver outreach.'}</span></div>
    </article>
    <article className="panel campaign-history">
      <div className="panel-heading"><div><div className="eyebrow">RECENT ACTIVITY</div><h2>Campaign log</h2></div><span className="record-count">{campaigns.length} rounds</span></div>
      {campaigns.length ? campaigns.map((campaign) => <div className="activity-item" key={campaign.id}><span className="activity-mark"><Bell size={15} /></span><div className="activity-content"><strong>Tier {campaign.stage} · {campaign.blood_group} · {campaign.district}</strong><span>{campaign.recipients_count} donor records · CBSRI {campaign.cbsri.toFixed(1)}{campaign.email_configured ? ` · ${campaign.emailed_count} emailed${campaign.email_failed_count ? ` · ${campaign.email_failed_count} failed` : ''}` : ''}</span><small>{campaign.donor_names.slice(0, 4).map((name) => name.replace(' (demo)', '')).join(', ') || 'No eligible recipients'}</small></div><span className="request-status">{campaign.status}</span></div>) : <div className="donor-empty"><Bell size={19} /><span>No campaign notifications yet.</span></div>}
    </article>
  </div>
}
