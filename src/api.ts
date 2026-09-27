import type { Advisory, AuthUser, BloodRequest, Campaign, Dashboard, Donor, DonorHistory, DonorNotification, Forecast, Inventory, LoginResult } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? '/api'
const TOKEN_KEY = 'raktsanket.access-token'
const USER_KEY = 'raktsanket.user'

export function getSessionUser(): AuthUser | null {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY) ?? 'null') as AuthUser | null
  } catch {
    return null
  }
}

export function saveSession(login: LoginResult) {
  sessionStorage.setItem(TOKEN_KEY, login.access_token)
  sessionStorage.setItem(USER_KEY, JSON.stringify(login.user))
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
}

export function hasSessionToken() {
  return Boolean(sessionStorage.getItem(TOKEN_KEY))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY)
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    if (response.status === 401 && import.meta.env.VITE_AUTH_REQUIRED === 'true') {
      clearSession()
      window.location.assign('/')
    }
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
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
  currentUser: () => request<AuthUser>('/auth/me'),
  createDonorAccount: (body: { donor_id: number; email: string; password: string }) => request<AuthUser>('/admin/donor-accounts', { method: 'POST', body: JSON.stringify(body) }),
}
