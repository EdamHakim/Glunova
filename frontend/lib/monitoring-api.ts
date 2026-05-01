const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

type Severity = 'info' | 'warning' | 'critical'

export type MonitoringAlert = {
  id: number
  patient_id: number
  patient_username: string
  severity: Severity
  title: string
  message: string
  status: 'active' | 'acknowledged' | 'resolved'
  triggered_at: string
  relative_time: string
}

export type MonitoringTimelineItem = {
  type: 'screening' | 'progression' | 'alert' | 'log' | 'lab_result'
  timestamp: string
  relative_time: string
  patient_id: number
  patient_username: string
  title: string
  description: string
  value: string
}

export type MonitoringTierSummary = {
  tier: 'low' | 'moderate' | 'high' | 'critical'
  count: number
  avg_score: number
  percentage: number
}

export type PatientLabResultRow = {
  id: number
  patient_id: string
  source_document_id: string
  source_document_filename: string
  source_document_created_at: string
  test_name: string
  normalized_name: string
  value: string
  numeric_value: number | null
  unit: string | null
  reference_range: string | null
  is_out_of_range: boolean | null
  observed_at: string | null
  raw_payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

async function getJson<T>(path: string) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export async function listMonitoringAlerts(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: MonitoringAlert[]; total: number }>(`/monitoring/alerts${query}`)
}

export async function listMonitoringTimeline(patientId?: string, limit = 30) {
  const query = new URLSearchParams({ limit: String(limit) })
  if (patientId) query.set('patient_id', patientId)
  return getJson<{ items: MonitoringTimelineItem[]; total: number }>(`/monitoring/timeline?${query.toString()}`)
}

export async function getMonitoringProgression(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ tiers: MonitoringTierSummary[]; total_patients: number }>(`/monitoring/progression${query}`)
}

export async function listLabResults(patientId: string) {
  const q = new URLSearchParams({ patient_id: patientId })
  return getJson<{ items: PatientLabResultRow[]; total: number }>(`/lab-results?${q.toString()}`)
}
