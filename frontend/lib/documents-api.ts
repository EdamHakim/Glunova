const base = () => process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8000'

export type ExtractedDocument = Record<string, unknown> & {
  medications?: Array<Record<string, unknown>>
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

export async function fetchCurrentUser(token: string) {
  const r = await fetch(`${base()}${process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ id: string; role: string; full_name: string }>
}

export async function listDocuments(token: string, patientId: string, page = 1, pageSize = 20) {
  const q = new URLSearchParams({ patient_id: patientId, page: String(page), page_size: String(pageSize) })
  const r = await fetch(`${base()}${process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'}/documents?${q}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ items: MedicalDocumentRow[]; total: number }>
}

export async function uploadDocument(token: string, patientId: string, file: File) {
  const fd = new FormData()
  fd.append('patient_id', patientId)
  fd.append('file', file)
  const r = await fetch(`${base()}${process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<MedicalDocumentRow>
}
