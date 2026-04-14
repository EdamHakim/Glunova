'use client'

import { useCallback, useEffect, useState } from 'react'
import { FileUp, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  fetchCurrentUser,
  listDocuments,
  uploadDocument,
  type ExtractedDocument,
  type MedicalDocumentRow,
} from '@/lib/documents-api'

const TOKEN_KEY = 'glunova_access_token'

function formatExtraction(ex: ExtractedDocument | null) {
  if (!ex) return null
  const skip = new Set(['medications'])
  const rows: [string, string][] = []
  for (const [k, v] of Object.entries(ex)) {
    if (skip.has(k)) continue
    if (v === null || v === undefined || v === '') continue
    rows.push([k, typeof v === 'object' ? JSON.stringify(v) : String(v)])
  }
  return rows
}

export function MedicalDocumentsSection() {
  const [token, setToken] = useState('')
  const [patientId, setPatientId] = useState('')
  const [role, setRole] = useState<string | null>(null)
  const [items, setItems] = useState<MedicalDocumentRow[]>([])
  const [selected, setSelected] = useState<MedicalDocumentRow | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    const t = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null
    if (t) setToken(t)
  }, [])

  const persistToken = (t: string) => {
    setToken(t)
    if (typeof window !== 'undefined') {
      if (t) localStorage.setItem(TOKEN_KEY, t)
      else localStorage.removeItem(TOKEN_KEY)
    }
  }

  const resolvePatient = useCallback(async () => {
    if (!token.trim()) {
      setError('Add an access token from login (POST /api/v1/auth/login).')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const me = await fetchCurrentUser(token.trim())
      setRole(me.role)
      let pid = patientId.trim()
      if (me.role === 'patient') {
        pid = me.id
        setPatientId(me.id)
      }
      if (!pid) {
        setError('Enter the patient UUID to load documents (doctors/caregivers).')
        setLoading(false)
        return
      }
      const list = await listDocuments(token.trim(), pid)
      setItems(list.items)
      setSelected(list.items[0] ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [token, patientId])

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !token.trim() || !patientId.trim()) return
    setUploading(true)
    setError(null)
    try {
      const doc = await uploadDocument(token.trim(), patientId.trim(), file)
      setItems((prev) => [doc, ...prev])
      setSelected(doc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const extraction = selected?.extracted_json ?? null
  const meds: Array<Record<string, unknown>> = Array.isArray(extraction?.medications)
    ? (extraction!.medications as Array<Record<string, unknown>>)
    : []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileUp className="h-5 w-5" />
          Medical documents (OCR)
        </CardTitle>
        <CardDescription>
          Upload lab reports, prescriptions, or clinical PDFs/images. Values are extracted from OCR and LLM
          refinement—always verify with a clinician. PHI: use a secure token and approved hosting.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="api-token">Access token (Bearer)</Label>
            <Input
              id="api-token"
              type="password"
              autoComplete="off"
              placeholder="Paste JWT from /api/v1/auth/login"
              value={token}
              onChange={(e) => persistToken(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="patient-id">Patient ID (UUID)</Label>
            <Input
              id="patient-id"
              placeholder="Auto-filled for patients after Load"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              disabled={role === 'patient'}
            />
          </div>
          <div className="flex items-end gap-2">
            <Button type="button" variant="secondary" onClick={() => void resolvePatient()} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="ml-2">Load account &amp; list</span>
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="file-up">Upload file (JPEG, PNG, WebP, PDF)</Label>
          <Input
            id="file-up"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            disabled={uploading || !patientId.trim() || !token.trim()}
            onChange={(e) => void onUpload(e)}
          />
          {uploading && <p className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Processing OCR…</p>}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <h4 className="text-sm font-medium mb-2">Recent uploads</h4>
            <ul className="space-y-2 max-h-48 overflow-y-auto border border-border rounded-md p-2">
              {items.length === 0 && <li className="text-sm text-muted-foreground">No documents yet.</li>}
              {items.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    className={`text-left w-full text-sm p-2 rounded hover:bg-muted ${selected?.id === d.id ? 'bg-muted' : ''}`}
                    onClick={() => setSelected(d)}
                  >
                    <span className="font-medium truncate block">{d.original_filename}</span>
                    <span className="text-xs text-muted-foreground flex gap-2 flex-wrap">
                      {d.document_type_detected && <Badge variant="outline">{d.document_type_detected}</Badge>}
                      <span>{new Date(d.created_at).toLocaleString()}</span>
                      {d.llm_refinement_status && <Badge variant="secondary">{d.llm_refinement_status}</Badge>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium mb-2">Extracted summary</h4>
            {!selected && <p className="text-sm text-muted-foreground">Select a document.</p>}
            {selected && (
              <div className="space-y-3 text-sm border border-border rounded-md p-3 max-h-96 overflow-y-auto">
                <dl className="space-y-1">
                  {formatExtraction(extraction)?.map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[1fr_2fr] gap-2">
                      <dt className="text-muted-foreground">{k}</dt>
                      <dd className="break-words">{v}</dd>
                    </div>
                  ))}
                </dl>
                {meds.length > 0 && (
                  <div>
                    <p className="font-medium mb-1">Medications</p>
                    <ul className="list-disc pl-4 space-y-1">
                      {meds.map((m, i) => (
                        <li key={i}>
                          {[m.name, m.dosage, m.frequency]
                            .map((x) => (typeof x === 'string' ? x : x != null ? String(x) : ''))
                            .filter(Boolean)
                            .join(' · ') || JSON.stringify(m)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {selected.raw_ocr_text && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground">Raw OCR text</summary>
                    <pre className="mt-2 whitespace-pre-wrap break-words max-h-40 overflow-y-auto bg-muted/50 p-2 rounded">
                      {selected.raw_ocr_text}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
