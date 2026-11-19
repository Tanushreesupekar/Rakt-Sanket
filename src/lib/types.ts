export type RiskLevel = 'critical' | 'elevated' | 'stable'

export interface Inventory {
  id: number
  district: string
  blood_group: string
  units_available: number
  avg_daily_demand: number
  safety_stock_units: number
  days_of_supply: number
  shortage_score: number
  risk_level: RiskLevel
  cbsri: number
  response_score: number
  eligible_donor_count: number
}

export interface Donor {
  id: number
  name: string
  district: string
  blood_group: string
  age: number
  last_donation_date: string | null
  donations_count: number
  response_rate: number
  response_probability: number
  notifications_30d: number
  last_contact_at: string | null
  available: boolean
  eligible: boolean
  priority_score: number
  explanation: string
}

export interface ForecastPoint {
  date: string
  projected_units: number
  demand_units: number
  shortage_score: number
  risk_level: RiskLevel
  explanation: string
}

export interface Forecast {
  district: string
  blood_group: string
  horizon_days: number
  current_units: number
  avg_daily_demand: number
  safety_stock_units: number
  cbsri: number
  response_score: number
  fatigue_adjusted_priority_score: number
  explanation: string
  points: ForecastPoint[]
}

export interface Campaign {
  id: number
  district: string
  blood_group: string
  stage: number
  recipients_count: number
  cbsri: number
  status: string
  created_at: string
  donor_names: string[]
  emailed_count: number
  email_failed_count: number
  email_configured: boolean
}

export interface EmailStatus {
  configured: boolean
  from_address: string | null
}

export interface Advisory {
  language: string
  title: string
  message: string
  action: string
  cbsri: number
}

export interface BloodRequest {
  id: number
  donor_id: number
  blood_group: string
  units_requested: number
  hospital_name: string
  district: string
  needed_by: string
  notes: string | null
  status: BloodRequestStatus
  created_at: string
  admin_note?: string | null
  reviewed_at?: string | null
}

export type BloodRequestStatus = 'pending review' | 'approved' | 'fulfilled' | 'rejected'

export interface AdminBloodRequest extends BloodRequest {
  donor_name: string
}

export interface DonorAccount {
  id: number
  email: string
  donor_id: number | null
  is_active: boolean
  created_at: string
}

export interface DonorHistory {
  donations_count: number
  last_donation_date: string | null
  donation_interval_days: number | null
  notifications_received: number
}

export interface DonorNotification {
  id: number
  created_at: string
  blood_group: string
  district: string
  stage: number
  cbsri: number
  status: string
  message: string
}

export interface AuthUser {
  id: number
  email: string
  role: 'admin' | 'donor'
  donor_id: number | null
}

export interface RegisterDonorInput {
  name: string
  email: string
  password: string
  district: string
  blood_group: string
  age: number
  last_donation_date: string | null
  donations_count: number
  consent: boolean
}

export interface LoginResult {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

export interface Dashboard {
  generated_at: string
  districts: string[]
  selected_district: string
  totals: {
    inventory_units: number
    donor_count: number
    eligible_donors: number
    at_risk_groups: number
    critical_groups: number
  }
  inventory: Inventory[]
  forecasts: Forecast[]
  top_donors: Donor[]
  recent_campaigns: Campaign[]
}
