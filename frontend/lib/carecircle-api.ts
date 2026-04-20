const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
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

export type CareCircleMember = {
  id: number
  name: string
  username: string
  role: string
  status: string
}

export type CareCircleUpdate = {
  id: number
  patient_id: number
  patient_name: string
  from_name: string
  summary: string
  created_at: string
}

export type CareCircleTask = {
  id: number
  patient_id: number
  patient_name: string
  title: string
  status: 'todo' | 'in_progress' | 'done'
  assignee_name: string
  due_at: string | null
  created_at: string
}

export type CareCirclePlan = {
  id: number
  patient_id: number
  patient_name: string
  doctor_name: string
  notes: string
  created_at: string
}

export type CareCircleMedicationGuidance = {
  id: number
  patient_id: number
  patient_name: string
  medication_name: string
  guidance: string
  doctor_validated: boolean
  created_at: string
}

export type CareCircleAppointment = {
  id: number
  patient_id: number
  patient_name: string
  doctor_name: string
  caregiver_name: string
  title: string
  starts_at: string
  ends_at: string
  status: 'scheduled' | 'completed' | 'cancelled'
  reminder_sent: boolean
}

export async function listCareCircleTeam(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: CareCircleMember[]; total: number }>(`/care-circle/team${query}`)
}

export async function listCareCircleUpdates(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: CareCircleUpdate[]; total: number }>(`/care-circle/updates${query}`)
}

export async function getCareCirclePlan(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{
    care_plans: CareCirclePlan[]
    tasks: CareCircleTask[]
    medication_guidance: CareCircleMedicationGuidance[]
  }>(`/care-circle/plan${query}`)
}

export async function listCareCircleAppointments(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: CareCircleAppointment[]; total: number }>(`/care-circle/appointments${query}`)
}
