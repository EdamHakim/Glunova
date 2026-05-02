const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

export type ExtractedDocument = Record<string, unknown> & {
  medications?: MedicationExtractionRow[]
}

export type MedicationVerification = {
  status?: 'matched' | 'ambiguous' | 'unverified' | 'failed'
  rxcui?: string | null
  name_display?: string | null
  candidates?: Array<Record<string, unknown>>
  note?: string | null
}

export type MedicationExtractionRow = Record<string, unknown> & {
  name?: string
  dosage?: string | null
  frequency?: string | null
  duration?: string | null
  route?: string | null
  instructions?: string | null
  verification?: MedicationVerification
}

export type MedicalDocumentRow = {
  id: string
  patient_id: string
  original_filename: string
  mime_type: string
  document_type_detected: string | null
  processing_status: string
  llm_refinement_status: string | null
  extracted_json: ExtractedDocument | null
  raw_ocr_text?: string | null
  created_at: string
}

export async function fetchCurrentUser() {
  const r = await fetch(`${base()}${apiPrefix()}/users/me`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ id: string; role: string; full_name: string }>
}

export async function listDocuments(patientId: string, page = 1, pageSize = 20) {
  const q = new URLSearchParams({ patient_id: patientId, page: String(page), page_size: String(pageSize) })
  const r = await fetch(`${base()}${apiPrefix()}/documents?${q}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ items: MedicalDocumentRow[]; total: number }>
}

export async function uploadDocument(patientId: string, file: File) {
  const fd = new FormData()
  fd.append('patient_id', patientId)
  fd.append('file', file)
  const r = await fetch(`${base()}${apiPrefix()}/documents`, {
    method: 'POST',
    credentials: 'include',
    body: fd,
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<MedicalDocumentRow>
}

export type DocumentDownloadResult =
  | { kind: 'url'; url: string }
  | { kind: 'blob'; blob: Blob; filename: string }

export async function requestDocumentDownload(docId: string): Promise<DocumentDownloadResult> {
  const r = await fetch(`${base()}${apiPrefix()}/documents/${docId}/download`, {
    credentials: 'include',
  })
  const ct = r.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const j = (await r.json().catch(() => ({}))) as { url?: string; detail?: string }
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Download failed')
    if (!j.url || typeof j.url !== 'string') throw new Error('No download URL returned')
    return { kind: 'url', url: j.url }
  }
  if (!r.ok) throw new Error(await r.text())
  const cd = r.headers.get('Content-Disposition') || ''
  const m = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(cd)
  const filename = m ? decodeURIComponent(m[1].replace(/"/g, '')) : 'document'
  return { kind: 'blob', blob: await r.blob(), filename }
}
