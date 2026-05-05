'use client'

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { Download, Loader2, ScanSearch, Upload } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { getApiUrls } from '@/lib/auth'
import { useAuth } from '@/components/auth-context'

type DFUResult = {
  patient_id: number
  ulcer_detected: boolean
  ulcer_area_ratio: number
  ulcer_area_px: number
  ulcer_area_mm2: number
  bbox_width_mm: number
  bbox_height_mm: number
  mm_per_pixel: number
  overlay_base64: string
}

export function DFUSegmentationPanel() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [mmPerPixel, setMmPerPixel] = useState('0.5')
  const [threshold, setThreshold] = useState('0.5')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DFUResult | null>(null)

  const areaPercent = useMemo(() => (result ? Math.round(result.ulcer_area_ratio * 100) : 0), [result])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setFile(selected)
    setError('')
    setResult(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)

    const pid = Number.parseInt(patientId.trim(), 10)
    const mm = Number.parseFloat(mmPerPixel)
    const thr = Number.parseFloat(threshold)
    if (!Number.isFinite(pid) || pid <= 0) return setError('Choose a patient from your list.')
    if (!Number.isFinite(mm) || mm <= 0) return setError('mm/pixel must be > 0.')
    if (!Number.isFinite(thr) || thr < 0 || thr > 1) return setError('Threshold must be between 0 and 1.')
    if (!file) return setError('Select a foot ulcer image.')
    if (!sessionUser || sessionUser.role !== 'doctor') return setError('This tool is only available to doctors.')

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const form = new FormData()
      form.append('patient_id', String(pid))
      form.append('image', file)
      form.append('threshold', String(thr))
      form.append('mm_per_pixel', String(mm))

      const res = await fetch(`${fastapi}/clinic/dfu-segmentation/infer`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(typeof body?.detail === 'string' ? body.detail : 'DFU analysis failed.')
      }
      const data = await res.json()
      setResult({
        patient_id: data.patient_id,
        ulcer_detected: data.ulcer_detected,
        ulcer_area_ratio: data.ulcer_area_ratio,
        ulcer_area_px: data.ulcer_area_px,
        ulcer_area_mm2: data.ulcer_area_mm2,
        bbox_width_mm: data.bbox_width_mm,
        bbox_height_mm: data.bbox_height_mm,
        mm_per_pixel: data.mm_per_pixel,
        overlay_base64: data.overlay_base64,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.')
    } finally {
      setLoading(false)
    }
  }

  async function downloadReport() {
    if (!file || !result) return
    const pid = Number.parseInt(patientId.trim(), 10)
    const mm = Number.parseFloat(mmPerPixel)
    const thr = Number.parseFloat(threshold)
    const { fastapi } = getApiUrls()
    const form = new FormData()
    form.append('patient_id', String(pid))
    form.append('image', file)
    form.append('threshold', String(thr))
    form.append('mm_per_pixel', String(mm))
    const res = await fetch(`${fastapi}/clinic/dfu-segmentation/report.pdf`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(typeof body?.detail === 'string' ? body.detail : 'Failed to generate PDF report.')
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dfu_report_patient_${pid}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  if (sessionLoading || sessionUser?.role !== 'doctor') return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ScanSearch className="h-5 w-5 text-primary" />
          Foot ulcer detection & segmentation
        </CardTitle>
        <CardDescription>
          Upload a foot image for a selected assigned patient to detect ulcer region, estimate lesion
          dimensions, view XAI overlay, and generate a PDF report for clinical documentation.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4 max-w-3xl">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2 sm:col-span-1 min-w-0">
              <DoctorPatientPicker
                id="dfu-patient-id"
                label="Patient"
                value={patientId}
                onChange={setPatientId}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dfu-mm-px">mm / pixel</Label>
              <Input id="dfu-mm-px" type="number" step="0.01" min="0.01" value={mmPerPixel} onChange={(e) => setMmPerPixel(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dfu-threshold">Threshold (0-1)</Label>
              <Input id="dfu-threshold" type="number" step="0.01" min="0" max="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="dfu-image">Foot ulcer image</Label>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input id="dfu-image" type="file" accept="image/*" onChange={onFileChange} className="cursor-pointer" />
              {previewUrl ? (
                <div className="h-24 w-24 shrink-0 overflow-hidden rounded-md border bg-muted">
                  <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                </div>
              ) : null}
            </div>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Run segmentation
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!result || loading}
              onClick={() => {
                void downloadReport().catch((e: unknown) =>
                  setError(e instanceof Error ? e.message : 'Failed to generate PDF report.'),
                )
              }}
            >
              <Download className="mr-2 h-4 w-4" />
              Download PDF report
            </Button>
          </div>
        </form>

        {result ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="space-y-2 rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Detection</span>
                <Badge variant={result.ulcer_detected ? 'destructive' : 'secondary'}>
                  {result.ulcer_detected ? 'Ulcer detected' : 'No ulcer detected'}
                </Badge>
              </div>
              <p className="text-sm">Mask coverage: {areaPercent}%</p>
              <p className="text-sm">Ulcer area: {result.ulcer_area_px} px ({result.ulcer_area_mm2.toFixed(2)} mm²)</p>
              <p className="text-sm">
                Lesion dimensions: {result.bbox_width_mm.toFixed(2)} mm × {result.bbox_height_mm.toFixed(2)} mm
              </p>
              <p className="text-xs text-muted-foreground">Calibration: {result.mm_per_pixel} mm/pixel</p>
            </div>
            <div className="rounded-lg border p-2">
              <p className="text-sm text-muted-foreground mb-2">XAI Overlay</p>
              <img
                src={`data:image/png;base64,${result.overlay_base64}`}
                alt="DFU segmentation overlay"
                className="w-full max-h-72 object-contain rounded bg-muted"
              />
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
