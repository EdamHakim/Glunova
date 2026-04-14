'use client'

import { ChangeEvent, FormEvent, useMemo, useState } from 'react'
import { Upload, Mic, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getAccessToken, getApiUrls } from '@/lib/auth'

type TongueResult = {
  probability: number
  prediction_label: string
  threshold_used: number
  heatmapBase64?: string
}

export default function ScreeningPage() {
  const [patientId, setPatientId] = useState('1')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tongueResult, setTongueResult] = useState<TongueResult | null>(null)
  const [isResultModalOpen, setIsResultModalOpen] = useState(false)

  const riskPercent = useMemo(() => {
    if (!tongueResult) return 0
    return Math.round(tongueResult.probability * 100)
  }, [tongueResult])

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setFile(selected)
    setError('')
    setTongueResult(null)
    setPreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  async function onTongueSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setTongueResult(null)

    if (!file) {
      setError('Please select an image before submitting.')
      return
    }
    const token = getAccessToken()
    if (!token) {
      setError('You must login first.')
      return
    }

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const payload = new FormData()
      payload.append('patient_id', patientId)
      payload.append('image', file)

      const response = await fetch(`${fastapi}/screening/tongue/infer`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: payload,
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Tongue screening request failed.')
      }
      const data = await response.json()
      const result = {
        probability: data.probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
        heatmapBase64: undefined,
      }

      const gradcamPayload = new FormData()
      gradcamPayload.append('patient_id', patientId)
      gradcamPayload.append('image', file)
      const gradcamResponse = await fetch(`${fastapi}/screening/tongue/gradcam`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: gradcamPayload,
      })
      if (gradcamResponse.ok) {
        const gradcamData = await gradcamResponse.json()
        result.heatmapBase64 = gradcamData.heatmap_base64
      }

      setTongueResult(result)
      setIsResultModalOpen(true)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <Dialog open={isResultModalOpen} onOpenChange={setIsResultModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tongue Screening Result</DialogTitle>
            <DialogDescription>
              AI prediction for patient ID {patientId}.
            </DialogDescription>
          </DialogHeader>

          {tongueResult ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Prediction</span>
                <Badge>{tongueResult.prediction_label}</Badge>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Probability</span>
                <span className="font-semibold">{Math.round(tongueResult.probability * 100)}%</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm text-muted-foreground">Threshold Used</span>
                <span className="font-semibold">{tongueResult.threshold_used}</span>
              </div>
              {tongueResult.heatmapBase64 ? (
                <div className="rounded-lg border p-2">
                  <p className="text-sm text-muted-foreground mb-2">Grad-CAM Heatmap</p>
                  <img
                    src={`data:image/jpeg;base64,${tongueResult.heatmapBase64}`}
                    alt="Tongue Grad-CAM"
                    className="w-full h-48 object-cover rounded"
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          <DialogFooter>
            <Button onClick={() => setIsResultModalOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div>
        <h1 className="text-3xl font-bold tracking-tight">Non-Invasive Screening</h1>
        <p className="text-muted-foreground mt-2">AI-powered health assessment using voice, tongue, and eye imaging</p>
      </div>

      {/* Upload Sections */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Voice Recording */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mic className="h-5 w-5 text-health-info" />
              Voice Recording
            </CardTitle>
            <CardDescription>Record patient voice sample</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border">
              <div className="text-center">
                <Mic className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Click to record</p>
              </div>
            </div>
            <Button variant="outline" className="w-full">
              Start Recording
            </Button>
          </CardContent>
        </Card>

        {/* Tongue Image */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Upload className="h-5 w-5 text-health-warning" />
              Tongue Image
            </CardTitle>
            <CardDescription>Upload and run PyTorch tongue diabetes inference</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <form className="space-y-3" onSubmit={onTongueSubmit}>
              <Input
                type="number"
                value={patientId}
                onChange={(event) => setPatientId(event.target.value)}
                placeholder="Patient ID"
                min={1}
                required
              />
              <Input type="file" accept="image/*" onChange={onFileChange} required />

              {previewUrl ? (
                <div className="rounded-lg border p-2">
                  <img src={previewUrl} alt="Tongue preview" className="h-36 w-full object-cover rounded" />
                </div>
              ) : null}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? 'Analyzing...' : 'Run Tongue Screening'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Eye Image */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Upload className="h-5 w-5 text-health-success" />
              Eye Image
            </CardTitle>
            <CardDescription>Upload eye/retina photo</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border hover:border-primary cursor-pointer transition-colors">
              <div className="text-center">
                <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Drag or click to upload</p>
              </div>
            </div>
            <Button variant="outline" className="w-full">
              Upload Image
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* AI Predictions */}
      <Card>
        <CardHeader>
          <CardTitle>AI Assessment Results</CardTitle>
          <CardDescription>Predictions from multi-modal analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 border border-border rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">Overall Risk Score</span>
                <Badge className="text-lg px-3 py-1">{riskPercent}</Badge>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-linear-to-r from-health-success via-health-warning to-health-danger h-2 rounded-full"
                  style={{ width: `${riskPercent}%` }}
                />
              </div>
              {tongueResult ? (
                <p className="text-xs text-muted-foreground mt-2">
                  Tongue result: <span className="font-medium">{tongueResult.prediction_label}</span> (threshold {tongueResult.threshold_used})
                </p>
              ) : (
                <p className="text-xs text-muted-foreground mt-2">Submit a tongue image to get model prediction.</p>
              )}
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            {tongueResult ? (
              <div className="rounded-lg border p-3">
                <p className="text-sm text-muted-foreground">Latest Tongue Result</p>
                <p className="font-semibold mt-1">
                  {tongueResult.prediction_label} ({Math.round(tongueResult.probability * 100)}%)
                </p>
                <Button variant="link" className="px-0 h-auto mt-1" onClick={() => setIsResultModalOpen(true)}>
                  View full details
                </Button>
              </div>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Voice Analysis</p>
                <p className="font-semibold text-health-success">Low Risk</p>
                <p className="text-xs text-muted-foreground mt-1">Normal respiratory pattern</p>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Tongue Examination</p>
                <p className="font-semibold text-health-warning">Moderate</p>
                <p className="text-xs text-muted-foreground mt-1">Slight coating detected</p>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Eye Examination</p>
                <p className="font-semibold text-health-danger">Requires Review</p>
                <p className="text-xs text-muted-foreground mt-1">Consult ophthalmologist</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Explainability */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            AI Explainability
          </CardTitle>
          <CardDescription>Grad-CAM & SHAP analysis of predictions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <p className="font-medium text-sm">Voice Features</p>
              <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                <p className="text-xs text-center text-muted-foreground">
                  Grad-CAM heatmap visualization
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-sm">Tongue Image</p>
              {tongueResult?.heatmapBase64 ? (
                <div className="bg-muted rounded-lg p-2 aspect-square">
                  <img
                    src={`data:image/jpeg;base64,${tongueResult.heatmapBase64}`}
                    alt="Tongue Grad-CAM heatmap"
                    className="h-full w-full rounded object-cover"
                  />
                </div>
              ) : (
                <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                  <p className="text-xs text-center text-muted-foreground">
                    Run tongue screening to generate Grad-CAM heatmap
                  </p>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <p className="font-medium text-sm">Feature Importance (SHAP)</p>
              <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                <p className="text-xs text-center text-muted-foreground">
                  Feature contribution chart
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
