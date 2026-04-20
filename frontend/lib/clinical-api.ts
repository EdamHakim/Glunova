const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') return `${window.location.protocol}//${window.location.hostname}:8000`
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

async function getJson<T>(path: string) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export type ClinicalSummary = {
  critical_cases: number
  high_risk: number
  stable: number
  pending_review: number
}

export type ClinicalPriorityRow = {
  id: number
  patient_id: number
  patient_name: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  summary: string
  status: 'pending' | 'in_review' | 'closed'
  created_at: string
}

export type ImagingQueueRow = {
  id: number
  patient_id: number
  patient_name: string
  analysis_type: 'cataract' | 'retinopathy' | 'foot_ulcer' | 'infrared'
  severity_grade: number
  confidence: number
  captured_at: string
}

export type PreconsultationRow = {
  id: number
  patient_id: number
  patient_name: string
  chief_complaint: string
  recommendation: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  created_at: string
}

export const getClinicalSummary = () => getJson<ClinicalSummary>('/clinical/summary')
export const listClinicalPriorities = () => getJson<{ items: ClinicalPriorityRow[]; total: number }>('/clinical/priorities')
export const listImagingQueue = () => getJson<{ items: ImagingQueueRow[]; total: number }>('/clinical/imaging-queue')
export const listPreconsultation = () => getJson<{ items: PreconsultationRow[]; total: number }>('/clinical/preconsultation')
