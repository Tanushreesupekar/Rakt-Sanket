import { useState } from 'react'
import { Check, Globe, RefreshCw, X } from 'lucide-react'
import { getApiBaseUrl, PRESET_SERVERS, setApiBaseUrl } from '../lib/api'

export default function ServerConfigModal({ onClose }: { onClose: () => void }) {
  const current = getApiBaseUrl()
  const [customUrl, setCustomUrl] = useState(current)
  const [testing, setTesting] = useState(false)
  const [testStatus, setTestStatus] = useState<{ ok: boolean; msg: string } | null>(null)

  async function testConnection(url: string) {
    setTesting(true)
    setTestStatus(null)
    const target = url.trim().replace(/\/+$/, '')
    try {
      const res = await fetch(`${target}/advisories?district=Amravati&language=en`, { signal: AbortSignal.timeout(4000) })
      if (res.ok) {
        setTestStatus({ ok: true, msg: 'Connected successfully to backend!' })
      } else {
        setTestStatus({ ok: false, msg: `Server responded with HTTP ${res.status}` })
      }
    } catch (e) {
      setTestStatus({ ok: false, msg: `Could not reach ${target}. Check IP & Wi-Fi.` })
    } finally {
      setTesting(false)
    }
  }

  function handleSave(url: string) {
    setApiBaseUrl(url)
    window.location.reload()
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ backgroundColor: '#fff', borderRadius: 12, maxWidth: 420, width: '100%', padding: 20, boxShadow: '0 20px 25px -5px rgba(0,0,0,0.3)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Globe size={18} color="#dc2626" />
            <strong style={{ fontSize: '1.05rem' }}>Backend Server Settings</strong>
          </div>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 16px', lineHeight: 1.4 }}>
          On mobile devices, the app must connect to the computer running the backend server. Choose your network or enter the PC's IP address.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', textTransform: 'uppercase' }}>Quick Presets:</span>
          {PRESET_SERVERS.map((preset) => {
            const isSelected = customUrl.trim().replace(/\/+$/, '') === preset.url.trim().replace(/\/+$/, '')
            return (
              <button
                key={preset.url}
                type="button"
                onClick={() => {
                  setCustomUrl(preset.url)
                  testConnection(preset.url)
                }}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: isSelected ? '2px solid #dc2626' : '1px solid #e2e8f0',
                  backgroundColor: isSelected ? '#fef2f2' : '#f8fafc',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: isSelected ? '#991b1b' : '#1e293b' }}>{preset.label}</div>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{preset.url}</div>
                </div>
                {isSelected && <Check size={16} color="#dc2626" />}
              </button>
            )
          })}
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
            Or Custom API URL:
          </label>
          <input
            type="text"
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            placeholder="http://192.168.1.X:8000/api"
            style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: '0.85rem' }}
          />
        </div>

        {testStatus && (
          <div style={{ marginBottom: 14, padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem', backgroundColor: testStatus.ok ? '#ecfdf5' : '#fef2f2', color: testStatus.ok ? '#065f46' : '#991b1b', border: `1px solid ${testStatus.ok ? '#a7f3d0' : '#fecaca'}` }}>
            {testStatus.msg}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            disabled={testing}
            onClick={() => testConnection(customUrl)}
            className="button button-outline"
            style={{ flex: 1, padding: '8px 12px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          >
            <RefreshCw size={14} className={testing ? 'button-spinner' : ''} />
            {testing ? 'Testing…' : 'Test Reachability'}
          </button>
          <button
            type="button"
            onClick={() => handleSave(customUrl)}
            className="button button-primary"
            style={{ flex: 1, padding: '8px 12px', fontSize: '0.85rem' }}
          >
            Save & Connect
          </button>
        </div>
      </div>
    </div>
  )
}
