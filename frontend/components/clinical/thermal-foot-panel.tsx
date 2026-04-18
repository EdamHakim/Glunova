'use client'

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { Footprints, Loader2, Upload } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getApiUrls } from '@/lib/auth'
import { useAuth } from '@/components/auth-context'

type ThermalFootResult = {
  patient_id: number
  probability: number
  prediction_label: string
  threshold_used: number
  model_name: string
  heatmapBase64?: string
}

export function ThermalFootPanel() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<ThermalFootResult | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const riskPercent = useMemo(() => {
    if (!result) return 0
    return Math.round(result.probability * 100)
  }, [result])

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
    if (!Number.isFinite(pid) || pid <= 0) {
      setError('Enter a valid patient ID (positive integer).')
      return
    }
    if (!file) {
      setError('Select a foot thermal / infrared image.')
      return
    }
    if (!sessionUser || sessionUser.role !== 'doctor') {
      setError('This tool is only available to doctor accounts.')
      return
    }

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()

      const inferForm = new FormData()
      inferForm.append('patient_id', String(pid))
      inferForm.append('image', file)

      const inferRes = await fetch(`${fastapi}/clinic/thermal-foot/infer`, {
        method: 'POST',
        credentials: 'include',
        body: inferForm,
      })
      if (!inferRes.ok) {
        const data = await inferRes.json().catch(() => ({}))
        throw new Error(
          typeof data?.detail === 'string' ? data.detail : 'Inference request failed.',
        )
      }
      const data = await inferRes.json()

      const next: ThermalFootResult = {
        patient_id: data.patient_id,
        probability: data.probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
        model_name: data.model_name,
      }

      const gradForm = new FormData()
      gradForm.append('patient_id', String(pid))
      gradForm.append('image', file)
      const gradRes = await fetch(`${fastapi}/clinic/thermal-foot/gradcam`, {
        method: 'POST',
        credentials: 'include',
        body: gradForm,
      })
      if (gradRes.ok) {
        const gradData = await gradRes.json()
        next.heatmapBase64 = gradData.heatmap_base64
      }

      setResult(next)
      setDialogOpen(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.')
    } finally {
      setLoading(false)
    }
  }

  if (sessionLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">Loading session…</CardContent>
      </Card>
    )
  }

  if (sessionUser?.role !== 'doctor') {
    return null
  }

  return (
    <>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Thermal foot analysis</DialogTitle>
            <DialogDescription>
              Model output for patient #{result?.patient_id ?? '—'}. For decision support only — not a
              standalone diagnosis.
            </DialogDescription>
          </DialogHeader>

          {result ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Prediction</span>
                <Badge variant={result.prediction_label === 'diabetes' ? 'destructive' : 'secondary'}>
                  {result.prediction_label}
                </Badge>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Diabetes probability</span>
                <span className="font-semibold">{riskPercent}%</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Threshold</span>
                <span className="font-semibold">{result.threshold_used}</span>
              </div>
              <p className="text-xs text-muted-foreground">Model: {result.model_name}</p>
              {result.heatmapBase64 ? (
                <div className="rounded-lg border p-2">
                  <p className="text-sm text-muted-foreground mb-2">Grad-CAM (XAI)</p>
                  <img
                    src={`data:image/jpeg;base64,${result.heatmapBase64}`}
                    alt="Grad-CAM overlay on thermal foot image"
                    className="w-full max-h-64 object-contain rounded bg-muted"
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Footprints className="h-5 w-5 text-primary" />
            Thermal foot (IR) — diabetes risk
          </CardTitle>
          <CardDescription>
            Upload a plantar thermal or infrared image and link it to a patient ID. The model returns a
            risk score with a Grad-CAM heatmap for interpretability.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4 max-w-xl">
            <div className="space-y-2">
              <Label htmlFor="thermal-patient-id">Patient ID</Label>
              <Input
                id="thermal-patient-id"
                type="number"
                min={1}
                step={1}
                placeholder="e.g. 42"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="thermal-image">Thermal / IR image</Label>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <Input
                  id="thermal-image"
                  type="file"
                  accept="image/*"
                  onChange={onFileChange}
                  className="cursor-pointer"
                />
                {previewUrl ? (
                  <div className="h-24 w-24 shrink-0 overflow-hidden rounded-md border bg-muted">
                    <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                  </div>
                ) : null}
              </div>
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Run analysis
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
