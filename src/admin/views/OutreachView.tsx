import { Check, Clock3, Mail, Radio, Send, ShieldCheck, TriangleAlert } from 'lucide-react'
import { bloodGroups } from '../components/shared'
import type { Campaign } from '../../lib/types'
import type { FormEvent } from 'react'

export function OutreachView({ campaigns, district, bloodGroup, setBloodGroup, stage, setStage, batchSize, setBatchSize, result, busy, emailConfigured, onSubmit }: { campaigns: Campaign[]; district: string; bloodGroup: string; setBloodGroup: (value: string) => void; stage: number; setStage: (value: number) => void; batchSize: number; setBatchSize: (value: number) => void; result: Campaign | null; busy: boolean; emailConfigured: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <div className="outreach-grid">
    <section className="panel campaign-panel">
      <div className="eyebrow">STAGED DONOR ACTIVATION</div>
      <h2>Prepare an outreach round</h2>
      <p className="panel-intro">A prioritized contact list is generated for review. {emailConfigured ? 'Donors with a linked login receive an email when you run the round.' : 'Email delivery is not configured, so rounds are recorded as simulated.'}</p>
      <form className="campaign-form" onSubmit={onSubmit}>
        <label>Blood group<select value={bloodGroup} onChange={(event) => setBloodGroup(event.target.value)}>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
        <div className="campaign-stage-label"><span>Activation tier</span><span>District · {district}</span></div>
        <div className="stage-selector">{[1, 2, 3].map((number) => <button type="button" key={number} className={`stage-option ${stage === number ? 'stage-active' : ''}`} onClick={() => setStage(number)}><span className="stage-number">0{number}</span><strong>{['Priority', 'Expanded', 'Wider'][number - 1]}</strong><small>{['Top ranked donors', 'Next eligible group', 'Remaining candidates'][number - 1]}</small></button>)}</div>
        <label>Donors in this batch<input type="number" min="1" max="100" value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} /></label>
        <button className="button button-primary full-button" disabled={busy}>{busy ? <><span className="button-spinner" />Preparing outreach…</> : <><Send size={16} />{emailConfigured ? 'Prepare list & send email' : 'Prepare contact list'}</>}</button>
        <div className="consent-note"><ShieldCheck size={15} /><span>{emailConfigured ? 'Email is sent only to selected donors who have a linked, active donor login. Review consent, donation interval and local eligibility before contact.' : 'SMTP is not configured. This round is stored as simulated; add SMTP settings to deliver email.'}</span></div>
      </form>
    </section>

    <section className="panel campaign-history">
      <div className="panel-heading"><div><div className="eyebrow">ACTIVITY LOG</div><h2>Recent rounds</h2></div><span className="record-count">{campaigns.length} saved</span></div>
      {result && <div className="campaign-result"><div className="result-mark"><Check size={17} /></div><div><strong>Tier {result.stage} outreach prepared</strong><span>{result.recipients_count} donors · {result.blood_group} · CBSRI {result.cbsri.toFixed(1)}</span>{result.email_configured ? <small><Mail size={12} />{result.emailed_count} email{result.emailed_count === 1 ? '' : 's'} sent{result.email_failed_count ? ` · ${result.email_failed_count} failed` : ''}</small> : <small><Mail size={12} />Email not configured — this round is simulated</small>}{result.donor_names.length > 0 && <small>{result.donor_names.join(' · ')}</small>}</div></div>}
      <div className="activity-list">{campaigns.length ? campaigns.map((campaign) => <div className="activity-item" key={campaign.id}><span className="activity-mark"><Radio size={15} /></span><div className="activity-content"><strong>Tier {campaign.stage} · {campaign.blood_group} activation</strong><span>{campaign.recipients_count} donor records · {campaign.district}{campaign.email_configured ? ` · ${campaign.emailed_count} emailed` : ''}</span><small>{campaign.donor_names.slice(0, 3).map((name) => name.replace(' (demo)', '')).join(', ') || 'No eligible donors in this tier'}</small></div><span className="request-status">{campaign.status}</span><time>{new Date(campaign.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</time></div>) : <div className="history-empty"><Clock3 size={19} /><span>No outreach rounds recorded yet.</span></div>}</div>
      <div className="history-footnote"><TriangleAlert size={14} />{emailConfigured ? 'Email is delivered through the configured SMTP server. Verify donor consent and delivery outcomes before operational use.' : 'Simulated activity only. Add SMTP settings to send email from outreach rounds.'}</div>
    </section>
  </div>
}
