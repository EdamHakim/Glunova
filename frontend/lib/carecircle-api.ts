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

async function postJson<T>(path: string, body?: unknown) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function deleteReq(path: string) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
}

// ── Existing types ────────────────────────────────────────────────────────────

export type CareCircleMember = {
  id: number
  name: string
  username: string
  role: string
  status: string
  specialization?: string
  hospital_affiliation?: string
  relationship?: string
  is_professional?: boolean
}

export type CareCircleUpdate = {
  id: number
  patient_id: number
  patient_name: string
  from_name: string
  summary: string
  created_at: string
  source: 'human' | 'agent'
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

// ── Link management types ─────────────────────────────────────────────────────

export type DoctorLink = {
  id: number
  doctor_id: number
  name: string
  username: string
  specialization: string
  hospital_affiliation: string
  linked_at: string
}

export type CaregiverLink = {
  id: number
  caregiver_id: number
  name: string
  username: string
  relationship: string
  is_professional: boolean
  status: 'pending' | 'accepted' | 'rejected'
  created_at: string
  responded_at: string | null
}

export type AvailableDoctor = {
  id: number
  name: string
  username: string
  specialization: string
  license_number: string
  hospital_affiliation: string
}

export type AvailableCaregiver = {
  id: number
  name: string
  username: string
  relationship: string
  is_professional: boolean
}

export type PendingInvitation = {
  id: number
  patient_id: number
  name: string
  username: string
  created_at: string
}

// ── Existing read-only calls ──────────────────────────────────────────────────

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

// ── Patient: doctor links ─────────────────────────────────────────────────────

export async function listMyDoctors() {
  return getJson<{ items: DoctorLink[]; total: number }>('/care-circle/my-doctor')
}

export async function linkDoctor(doctorId: number) {
  return postJson<DoctorLink>('/care-circle/my-doctor', { doctor_id: doctorId })
}

export async function unlinkDoctor(linkId: number) {
  return deleteReq(`/care-circle/my-doctor/${linkId}`)
}

export async function listAvailableDoctors() {
  return getJson<{ items: AvailableDoctor[]; total: number }>('/care-circle/available-doctors')
}

// ── Patient: caregiver invitations ────────────────────────────────────────────

export async function listMyCaregivers() {
  return getJson<{ items: CaregiverLink[]; total: number }>('/care-circle/my-caregiver')
}

export async function inviteCaregiver(caregiverId: number) {
  return postJson<CaregiverLink>('/care-circle/my-caregiver', { caregiver_id: caregiverId })
}

export async function removeCaregiver(linkId: number) {
  return deleteReq(`/care-circle/my-caregiver/${linkId}`)
}

export async function listAvailableCaregivers() {
  return getJson<{ items: AvailableCaregiver[]; total: number }>('/care-circle/available-caregivers')
}

// ── Caregiver: invitation inbox ───────────────────────────────────────────────

export async function listPendingInvitations() {
  return getJson<{ items: PendingInvitation[]; total: number }>('/care-circle/pending-invitations')
}

export async function respondInvitation(linkId: number, action: 'accept' | 'reject') {
  return postJson<{ id: number; status: string; responded_at: string }>(
    `/care-circle/pending-invitations/${linkId}/respond`,
    { action },
  )
}
