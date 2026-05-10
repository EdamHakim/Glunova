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

export type CareCircleUpdate = {
  id: number
  patient_id: number
  patient_name: string
  from_name: string
  summary: string
  created_at: string
  source: 'human' | 'agent'
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
  booking_slot_id?: number | null
}

export type DoctorAppointmentSlot = {
  id: number
  doctor_id: number
  starts_at: string
  ends_at: string
  is_booked: boolean
  created_at: string
}

export type BookableSlot = {
  id: number
  doctor_id: number
  starts_at: string
  ends_at: string
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

export async function listCareCircleUpdates(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: CareCircleUpdate[]; total: number }>(`/care-circle/updates${query}`)
}

export async function listCareCircleAppointments(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<{ items: CareCircleAppointment[]; total: number }>(`/care-circle/appointments${query}`)
}

// ── Doctor weekly availability ────────────────────────────────────────────────

export type DoctorAvailability = {
  id: number
  doctor_id: number
  day_of_week: number  // 0=Mon … 6=Sun
  start_time: string   // "HH:MM"
  end_time: string
  slot_duration_min: number
  lunch_start: string | null
  lunch_end: string | null
}

export type AvailableTimeSlot = {
  starts_at: string  // ISO datetime
  ends_at: string
}

export async function getMyAvailability() {
  return getJson<{ items: DoctorAvailability[] }>('/care-circle/my-availability')
}

export async function saveMyAvailability(body: {
  schedule: { day_of_week: number; start_time: string; end_time: string }[]
  slot_duration_min: number
  lunch_start: string | null
  lunch_end: string | null
}) {
  return postJson<{ items: DoctorAvailability[] }>('/care-circle/my-availability', body)
}

export async function getDoctorAvailability(doctorId: number, opts?: { patientId?: string }) {
  const params = new URLSearchParams()
  params.set('doctor_id', String(doctorId))
  if (opts?.patientId) params.set('patient_id', opts.patientId)
  return getJson<{ items: DoctorAvailability[] }>(`/care-circle/doctor-availability?${params}`)
}

export async function getAvailableTimes(doctorId: number, date: string, opts?: { patientId?: string }) {
  const params = new URLSearchParams()
  params.set('doctor_id', String(doctorId))
  params.set('date', date)
  if (opts?.patientId) params.set('patient_id', opts.patientId)
  return getJson<{ items: AvailableTimeSlot[]; date: string }>(`/care-circle/available-times?${params}`)
}

export async function directBookAppointment(body: {
  doctor_id: number
  starts_at: string
  title?: string
  patient_id?: number
}) {
  return postJson<CareCircleAppointment>('/care-circle/book-direct', body)
}

// ── Doctor: availability slots (legacy pre-created slots) ─────────────────────

export async function listMyAppointmentSlots() {
  return getJson<{ items: DoctorAppointmentSlot[]; total: number }>('/care-circle/my-appointment-slots')
}

export async function createAppointmentSlot(body: { starts_at: string; ends_at: string }) {
  return postJson<DoctorAppointmentSlot>('/care-circle/my-appointment-slots', body)
}

export async function bulkCreateAppointmentSlots(slots: { starts_at: string; ends_at: string }[]) {
  return postJson<{ created: number; skipped: number; items: DoctorAppointmentSlot[] }>(
    '/care-circle/my-appointment-slots/bulk',
    { slots },
  )
}

export async function deleteAppointmentSlot(slotId: number) {
  return deleteReq(`/care-circle/my-appointment-slots/${slotId}`)
}

// ── Patient / caregiver: book from doctor slots ──────────────────────────────────

/** Caregiver must pass `patientId`; patients omit it (book for self). */
export async function listBookingDoctorsForPatient(patientId: string) {
  const q = `?patient_id=${encodeURIComponent(patientId)}`
  return getJson<{ items: DoctorLink[]; total: number }>(`/care-circle/booking/doctors${q}`)
}

export async function listBookableSlots(doctorId: number, opts?: { patientId?: string }) {
  const params = new URLSearchParams()
  params.set('doctor_id', String(doctorId))
  if (opts?.patientId) params.set('patient_id', opts.patientId)
  return getJson<{ items: BookableSlot[]; total: number }>(`/care-circle/bookable-slots?${params}`)
}

export async function bookAppointment(body: {
  slot_id: number
  title?: string
  /** Required when the caregiver books for a linked patient. */
  patient_id?: number
}) {
  return postJson<CareCircleAppointment>('/care-circle/book-appointment', body)
}

export async function cancelAppointment(appointmentId: number) {
  return postJson<CareCircleAppointment>(`/care-circle/appointments/${appointmentId}/cancel`)
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
