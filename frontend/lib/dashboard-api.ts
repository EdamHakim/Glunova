const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') return `${window.location.protocol}//${window.location.hostname}:8000`
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

export type DashboardOverview = {
  stats: {
    active_patients: number
    pending_screenings: number
    alerts: number
    avg_risk_score: number
  }
  trend: Array<{
    date: string
    risk_score: number
    confidence: number
  }>
  recent_patients: Array<{
    id: number
    name: string
    risk_level: 'Low' | 'Moderate' | 'High' | 'Critical'
    last_assessment: string
    status: string
  }>
}

export async function getDashboardOverview() {
  const response = await fetch(`${base()}${apiPrefix()}/dashboard/overview`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<DashboardOverview>
}

export type AssignedPatientRow = {
  id: number
  username: string
  display_name: string
}

/** Patients the signed-in viewer may scope to: doctors (assigned) or caregivers (accepted links). */
export async function getLinkedPatientsForDashboard() {
  const response = await fetch(`${base()}${apiPrefix()}/dashboard/my-patients`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<{ items: AssignedPatientRow[] }>
}

/** @deprecated Use {@link getLinkedPatientsForDashboard} */
export async function getDoctorAssignedPatients() {
  return getLinkedPatientsForDashboard()
}
