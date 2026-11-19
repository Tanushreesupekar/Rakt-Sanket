import { useState, type FormEvent } from 'react'
import { Check, Clock3, Mail, Radio, Send, ShieldCheck, TriangleAlert } from 'lucide-react'
import { bloodGroups } from '../components/shared'
import type { Campaign } from '../../lib/types'
import { api } from '../../lib/api'

export function OutreachView({ campaigns, district: _district, bloodGroup, setBloodGroup, stage: _stage, setStage: _setStage, batchSize: _batchSize, setBatchSize: _setBatchSize, result, busy, emailConfigured, onSubmit }: { campaigns: Campaign[]; district?: string; bloodGroup: string; setBloodGroup: (value: string) => void; stage?: number; setStage?: (value: number) => void; batchSize?: number; setBatchSize?: (value: number) => void; result: Campaign | null; busy: boolean; emailConfigured: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const [testEmailAddr, setTestEmailAddr] = useState('')
  const [testSending, setTestSending] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null)

  async function handleSendTest() {
    setTestSending(true)
    setTestResult(null)
    try {
      const res = await api.testEmail(testEmailAddr.trim() || undefined)
      setTestResult({ ok: true, text: res.message })
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof Error ? err.message : 'Test email failed. Check SMTP credentials in backend/.env' })
    } finally {
      setTestSending(false)
    }
  }

  return <div className="outreach-grid">
    <section className="panel campaign-panel">
      <div className="eyebrow">DONOR OUTREACH</div>
      <h2>Send outreach email</h2>
      <p className="panel-intro">Send notification emails to all registered donors. {emailConfigured ? 'Emails are dispatched directly to donor inboxes via SMTP.' : 'Email delivery is not configured, so rounds are recorded as simulated.'}</p>
      <form className="campaign-form" onSubmit={onSubmit}>
        <label>Blood group target
          <select value={bloodGroup} onChange={(event) => setBloodGroup(event.target.value)}>
            {bloodGroups.map((group) => <option key={group}>{group}</option>)}
          </select>
        </label>
        <button className="button button-primary full-button" disabled={busy} style={{ marginTop: 14 }}>
          {busy ? <><span className="button-spinner" />Sending outreach emails…</> : <><Send size={16} />Send Email to All Donors</>}
        </button>
        <div className="consent-note"><ShieldCheck size={15} /><span>{emailConfigured ? 'Email is sent to all registered donors via your configured SMTP provider.' : 'SMTP is not configured. Add SMTP credentials in backend/.env to deliver live email.'}</span></div>
      </form>

      <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-color, #e2e8f0)' }}>
        <div className="eyebrow">SMTP DIAGNOSTICS</div>
        <h3 style={{ fontSize: '0.95rem', margin: '4px 0 8px', fontWeight: 600 }}>Test email delivery</h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted, #64748b)', margin: '0 0 10px' }}>
          {emailConfigured ? 'SMTP is enabled. Send a test email to verify credentials and inbox delivery.' : 'SMTP is not configured yet. Set SMTP credentials in backend/.env.'}
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="email"
            placeholder="Recipient email address"
            value={testEmailAddr}
            onChange={(e) => setTestEmailAddr(e.target.value)}
            style={{ flex: 1, padding: '6px 10px', fontSize: '0.85rem', borderRadius: 6, border: '1px solid #cbd5e1' }}
          />
          <button
            type="button"
            className="button button-outline"
            style={{ whiteSpace: 'nowrap', padding: '6px 14px' }}
            disabled={testSending || !emailConfigured}
            onClick={handleSendTest}
          >
            {testSending ? 'Sending…' : 'Send test'}
          </button>
        </div>
        {testResult && (
          <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, fontSize: '0.82rem', backgroundColor: testResult.ok ? '#ecfdf5' : '#fef2f2', color: testResult.ok ? '#065f46' : '#991b1b', border: `1px solid ${testResult.ok ? '#a7f3d0' : '#fecaca'}` }}>
            {testResult.text}
          </div>
        )}
      </div>
    </section>

    <section className="panel campaign-history">
      <div className="panel-heading"><div><div className="eyebrow">ACTIVITY LOG</div><h2>Recent rounds</h2></div><span className="record-count">{campaigns.length} saved</span></div>
      {result && <div className="campaign-result"><div className="result-mark"><Check size={17} /></div><div><strong>Tier {result.stage} outreach prepared</strong><span>{result.recipients_count} donors · {result.blood_group} · CBSRI {result.cbsri.toFixed(1)}</span>{result.email_configured ? <small><Mail size={12} />{result.emailed_count} email{result.emailed_count === 1 ? '' : 's'} sent{result.email_failed_count ? ` · ${result.email_failed_count} failed` : ''}</small> : <small><Mail size={12} />Email not configured — this round is simulated</small>}{result.donor_names.length > 0 && <small>{result.donor_names.join(' · ')}</small>}</div></div>}
      <div className="activity-list">{campaigns.length ? campaigns.map((campaign) => <div className="activity-item" key={campaign.id}><span className="activity-mark"><Radio size={15} /></span><div className="activity-content"><strong>Tier {campaign.stage} · {campaign.blood_group} activation</strong><span>{campaign.recipients_count} donor records · {campaign.district}{campaign.email_configured ? ` · ${campaign.emailed_count} emailed` : ''}</span><small>{campaign.donor_names.slice(0, 3).map((name) => name.replace(' (demo)', '')).join(', ') || 'No eligible donors in this tier'}</small></div><span className="request-status">{campaign.status}</span><time>{new Date(campaign.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</time></div>) : <div className="history-empty"><Clock3 size={19} /><span>No outreach rounds recorded yet.</span></div>}</div>
      <div className="history-footnote"><TriangleAlert size={14} />{emailConfigured ? 'Email is delivered through the configured SMTP server. Verify donor consent and delivery outcomes before operational use.' : 'Simulated activity only. Add SMTP settings to send email from outreach rounds.'}</div>
    </section>
  </div>
}
