import { Capacitor } from '@capacitor/core'
import type { AdminBloodRequest, Advisory, AuthUser, BloodRequest, BloodRequestStatus, DonorAccount, Campaign, Dashboard, Donor, DonorHistory, DonorNotification, EmailStatus, Forecast, Inventory, LoginResult, RegisterDonorInput } from './types'

const TOKEN_KEY = 'raktsanket.access-token'
const USER_KEY = 'raktsanket.user'

export const PRESET_SERVERS = [
  { label: 'Wi-Fi (192.168.1.8)', url: 'http://192.168.1.8:8000/api' },
  { label: 'Ethernet (192.168.1.25)', url: 'http://192.168.1.25:8000/api' },
  { label: 'Android Emulator (10.0.2.2)', url: 'http://10.0.2.2:8000/api' },
  { label: 'Localhost (Web dev)', url: '/api' },
]

export function isNativePlatform(): boolean {
  try {
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('raktsanket_api_url')
    if (custom) return custom.replace(/\/+$/, '')
    if (isNativePlatform()) {
      return 'http://192.168.1.8:8000/api'
    }
  }
  return import.meta.env.VITE_API_URL ?? '/api'
}

export function setApiBaseUrl(url: string) {
  if (typeof window !== 'undefined') {
    if (!url.trim()) {
      localStorage.removeItem('raktsanket_api_url')
    } else {
      localStorage.setItem('raktsanket_api_url', url.trim())
    }
  }
}

export function getSessionUser(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY) ?? localStorage.getItem(USER_KEY)
    return JSON.parse(raw ?? 'null') as AuthUser | null
  } catch {
    return null
  }
}

export function saveSession(login: LoginResult) {
  sessionStorage.setItem(TOKEN_KEY, login.access_token)
  sessionStorage.setItem(USER_KEY, JSON.stringify(login.user))
  localStorage.setItem(TOKEN_KEY, login.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(login.user))
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function hasSessionToken() {
  return Boolean(sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY)
  const baseUrl = getApiBaseUrl()
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    })
  } catch (fetchErr) {
    const msg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr)
    throw new Error(`Cannot reach server at "${baseUrl}". Check that the backend is running and your phone is on the same Wi-Fi. (${msg})`)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    // a 401 on the sign-in request itself is a wrong password, not an expired session
    if (response.status === 401 && import.meta.env.VITE_AUTH_REQUIRED === 'true' && path !== '/auth/login') {
      clearSession()
      window.location.assign('/')
    }
    throw new Error(errorMessage(body?.detail, response.status))
  }
  return response.json() as Promise<T>
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string }

// FastAPI sends `detail` as a string for HTTPException and as a list of
// issues for request-validation (422) errors.
function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return (detail as ValidationIssue[]).map((issue) => {
      const field = issue.loc?.filter((part) => part !== 'body').join('.')
      const message = (issue.msg ?? 'is invalid').replace(/^Value error, /, '')
      return field ? `${field.replace(/_/g, ' ')}: ${message}` : message
    }).join('; ')
  }
  if (status === 429) return 'Too many attempts. Please wait a few minutes and try again.'
  return `Request failed (${status})`
}

export const api = {
  dashboard: (district?: string) => request<Dashboard>(`/dashboard${district ? `?district=${encodeURIComponent(district)}` : ''}`),
  donors: (district?: string) => request<Donor[]>(`/donors${district ? `?district=${encodeURIComponent(district)}` : ''}`),
  campaigns: () => request<Campaign[]>('/campaigns'),
  advisory: (district: string, language: string) => request<Advisory>(`/advisories?district=${encodeURIComponent(district)}&language=${language}`),
  forecasts: (district: string, bloodGroup: string, days = 14) => request<Forecast[]>(`/forecasts?district=${encodeURIComponent(district)}&blood_group=${encodeURIComponent(bloodGroup)}&days=${days}`),
  updateInventory: (id: number, body: Pick<Inventory, 'units_available' | 'avg_daily_demand' | 'safety_stock_units'>) => request<Inventory>(`/inventory/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  createDonor: (body: Pick<Donor, 'name' | 'district' | 'blood_group' | 'age' | 'last_donation_date' | 'donations_count' | 'response_rate'>) => request<Donor>('/donors', { method: 'POST', body: JSON.stringify(body) }),
  createCampaign: (body: { district: string; blood_group: string; stage: number; batch_size: number }) => request<Campaign>('/campaigns', { method: 'POST', body: JSON.stringify(body) }),
  donorProfile: (id: number) => request<Donor>(`/donors/${id}/profile`),
  updateDonorProfile: (id: number, body: Pick<Donor, 'name' | 'age' | 'available'>) => request<Donor>(`/donors/${id}/profile`, { method: 'PATCH', body: JSON.stringify(body) }),
  donorHistory: (id: number) => request<DonorHistory>(`/donors/${id}/history`),
  donorNotifications: (id: number) => request<DonorNotification[]>(`/donors/${id}/notifications`),
  bloodRequests: (id: number) => request<BloodRequest[]>(`/blood-requests?donor_id=${id}`),
  createBloodRequest: (body: Omit<BloodRequest, 'id' | 'status' | 'created_at'>) => request<BloodRequest>('/blood-requests', { method: 'POST', body: JSON.stringify(body) }),
  login: (email: string, password: string) => request<LoginResult>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  registerDonor: (body: RegisterDonorInput) => request<LoginResult>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  currentUser: () => request<AuthUser>('/auth/me'),
  switchRole: (role: 'admin' | 'donor') => request<LoginResult>(`/auth/switch-role?target_role=${role}`, { method: 'POST' }),
  createDonorAccount: (body: { donor_id: number; email: string; password: string }) => request<AuthUser>('/admin/donor-accounts', { method: 'POST', body: JSON.stringify(body) }),
  donorAccounts: () => request<DonorAccount[]>('/admin/donor-accounts'),
  emailStatus: () => request<EmailStatus>('/admin/email-status'),
  testEmail: (toEmail?: string) => request<{ ok: boolean; message: string }>('/admin/test-email', { method: 'POST', body: JSON.stringify(toEmail ? { to_email: toEmail } : {}) }),
  adminBloodRequests: (district?: string) => request<AdminBloodRequest[]>(`/admin/blood-requests${district ? `?district=${encodeURIComponent(district)}` : ''}`),
  reviewBloodRequest: (id: number, body: { status: Exclude<BloodRequestStatus, 'pending review'>; note?: string }) => request<AdminBloodRequest>(`/admin/blood-requests/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
}
