'use client'

import { useCallback, useEffect, useState } from 'react'
import { Download, FileUp, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  listDocuments,
  requestDocumentDownload,
  uploadDocument,
  type ExtractedDocument,
  type MedicationExtractionRow,
  type MedicalDocumentRow,
} from '@/lib/documents-api'

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

import { useAuth } from '@/components/auth-context'

function getVerificationBadgeClass(status?: string) {
  switch (status) {
    case 'matched':
      return 'bg-health-success/10 text-health-success border-health-success/20'
    case 'ambiguous':
      return 'bg-health-warning/10 text-health-warning border-health-warning/20'
    case 'failed':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    default:
      return 'bg-muted text-muted-foreground border-border'
  }
}

export function MedicalDocumentsSection() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [items, setItems] = useState<MedicalDocumentRow[]>([])
  const [selected, setSelected] = useState<MedicalDocumentRow | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)

  // Automatically resolve patient and load documents on mount/user change
  useEffect(() => {
    if (user) {
      if (user.role === 'patient') {
        setPatientId(user.id)
      }
    }
  }, [user])

  const resolveDocuments = useCallback(async (pid: string) => {
    if (!pid) return
    setLoading(true)
    setError(null)
    try {
      const list = await listDocuments(pid)
      setItems(list.items)
      setSelected(list.items[0] ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (patientId) {
      resolveDocuments(patientId)
    }
  }, [patientId, resolveDocuments])

  const onDownload = async () => {
    if (!selected) return
    setDownloadBusy(true)
    setError(null)
    try {
      const result = await requestDocumentDownload(selected.id)
      if (result.kind === 'url') {
        window.open(result.url, '_blank', 'noopener,noreferrer')
      } else {
        const href = URL.createObjectURL(result.blob)
        const a = document.createElement('a')
        a.href = href
        a.download = result.filename
        a.click()
        URL.revokeObjectURL(href)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloadBusy(false)
    }
  }

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !patientId.trim()) return
    setUploading(true)
    setError(null)
    try {
      const doc = await uploadDocument(patientId.trim(), file)
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
  const meds: MedicationExtractionRow[] = Array.isArray(extraction?.medications)
    ? extraction!.medications
    : []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileUp className="h-5 w-5" />
          Medical documents
        </CardTitle>
        <CardDescription>
          Your health records are analyzed automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {user?.role !== 'patient' && (
          <div className="flex items-end gap-2 mb-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="patient-id">Patient ID</Label>
              <Input
                id="patient-id"
                placeholder="Enter patient ID to view records"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="file-up">Upload new document</Label>
          <Input
            id="file-up"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            disabled={uploading || !patientId}
            onChange={(e) => void onUpload(e)}
          />
          {uploading && <p className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Analyzing Document...</p>}
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
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full sm:w-auto"
                  disabled={downloadBusy}
                  onClick={() => void onDownload()}
                >
                  {downloadBusy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  <span className="ml-2">Download original</span>
                </Button>
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
                        <li key={i} className="space-y-1">
                          <div>
                            {[m.name, m.dosage, m.frequency]
                              .map((x) => (typeof x === 'string' ? x : x != null ? String(x) : ''))
                              .filter(Boolean)
                              .join(' · ') || JSON.stringify(m)}
                          </div>
                          {m.instructions && (
                            <div className="text-[11px] italic text-muted-foreground leading-tight">
                              Dir: {m.instructions}
                            </div>
                          )}
                          {m.verification && (
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <Badge variant="outline" className={getVerificationBadgeClass(m.verification.status)}>
                                {m.verification.status ?? 'unverified'}
                              </Badge>
                              {m.verification.name_display && <span>RxNorm: {m.verification.name_display}</span>}
                              {m.verification.rxcui && <span>RxCUI {m.verification.rxcui}</span>}
                              {m.verification.note && (
                                <span className="text-muted-foreground">{m.verification.note}</span>
                              )}
                            </div>
                          )}
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
