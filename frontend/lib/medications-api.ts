const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

export type MedicationVerificationStatus = 'matched' | 'ambiguous' | 'unverified' | 'failed'

export type PatientMedicationRow = {
  id: number
  patient_id: string
  source_document_id: string
  source_document_filename: string
  source_document_created_at: string
  source_document_mime_type: string
  source_document_preview_url: string | null
  source_document_count: number
  name_raw: string
  name_display: string | null
  rxcui: string | null
  dosage: string | null
  frequency: string | null
  duration: string | null
  route: string | null
  instructions: string | null
  verification_status: MedicationVerificationStatus
  verification_detail: Record<string, unknown>
  created_at: string
  updated_at: string
}

export async function listMedications(patientId: string) {
  const q = new URLSearchParams({ patient_id: patientId })
  const r = await fetch(`${base()}${apiPrefix()}/medications?${q}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ items: PatientMedicationRow[]; total: number }>
}
