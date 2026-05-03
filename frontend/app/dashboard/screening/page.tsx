'use client'

import { ChangeEvent, FormEvent, useMemo, useState } from 'react'
import { Upload, Mic, AlertCircle, Eye } from 'lucide-react'
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
import { getApiUrls } from '@/lib/auth'
import RoleGuard from '@/components/auth/role-guard'

type TongueResult = {
  probability: number
  prediction_label: string
  threshold_used: number
  heatmapBase64?: string
}

type CataractResult = {
  prediction_label: string
  prediction_index: number
  confidence: number
  p_cataract: number
  probabilities: Record<string, number>
  heatmapBase64?: string
}

import { useAuth } from '@/components/auth-context'

export default function ScreeningPage() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()

  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tongueResult, setTongueResult] = useState<TongueResult | null>(null)
  const [isResultModalOpen, setIsResultModalOpen] = useState(false)

  // ─── Cataract (Eye Image) state ───
  const [eyeFile, setEyeFile] = useState<File | null>(null)
  const [eyePreviewUrl, setEyePreviewUrl] = useState('')
  const [eyeLoading, setEyeLoading] = useState(false)
  const [eyeError, setEyeError] = useState('')
  const [cataractResult, setCataractResult] = useState<CataractResult | null>(null)
  const [isCataractModalOpen, setIsCataractModalOpen] = useState(false)

  function onEyeFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setEyeFile(selected)
    setEyeError('')
    setCataractResult(null)
    setEyePreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  async function onCataractSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setEyeError('')
    setCataractResult(null)

    if (!eyeFile) {
      setEyeError('Please select an eye image before uploading.')
      return
    }
    if (!sessionUser || sessionUser.role !== 'patient' || sessionUser.userId == null) {
      setEyeError('Cataract screening requires a logged-in patient account.')
      return
    }

    setEyeLoading(true)
    try {
      const { fastapi } = getApiUrls()

      const inferPayload = new FormData()
      inferPayload.append('image', eyeFile)
      const inferResponse = await fetch(`${fastapi}/screening/cataract/infer`, {
        method: 'POST',
        credentials: 'include',
        body: inferPayload,
      })
      if (!inferResponse.ok) {
        const data = await inferResponse.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Cataract inference failed.')
      }
      const inferData = await inferResponse.json()

      const result: CataractResult = {
        prediction_label: inferData.prediction_label,
        prediction_index: inferData.prediction_index,
        confidence: inferData.confidence,
        p_cataract: inferData.p_cataract,
        probabilities: inferData.probabilities,
      }

      // Try to also fetch the Grad-CAM (best-effort)
      const gradcamPayload = new FormData()
      gradcamPayload.append('image', eyeFile)
      const gradcamResponse = await fetch(`${fastapi}/screening/cataract/gradcam`, {
        method: 'POST',
        credentials: 'include',
        body: gradcamPayload,
      })
      if (gradcamResponse.ok) {
        const gradcamData = await gradcamResponse.json()
        result.heatmapBase64 = gradcamData.heatmap_base64
      }

      setCataractResult(result)
      setIsCataractModalOpen(true)
    } catch (submitError) {
      setEyeError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setEyeLoading(false)
    }
  }

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

    if (!sessionUser) {
      setError('You must login first.')
      return
    }
    
    if (sessionUser.role !== 'patient' || sessionUser.userId == null) {
      setError('Screening is only available to patient accounts with a valid session.')
      return
    }

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const payload = new FormData()
      payload.append('image', file)

      const response = await fetch(`${fastapi}/screening/tongue/infer`, {
        method: 'POST',
        credentials: 'include',
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
      gradcamPayload.append('image', file)
      const gradcamResponse = await fetch(`${fastapi}/screening/tongue/gradcam`, {
        method: 'POST',
        credentials: 'include',
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

  if (sessionLoading) {
    return (
      <div className="space-y-6 p-4 sm:p-6">
        <p className="text-sm text-muted-foreground">Loading session…</p>
      </div>
    )
  }

  return (
    <RoleGuard
      allowedRoles={['patient']}
      title="Screening unavailable"
      description="Self-service screening is limited to patient accounts."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <Dialog open={isResultModalOpen} onOpenChange={setIsResultModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Tongue Screening Result</DialogTitle>
              <DialogDescription>AI prediction for your screening (account #{sessionUser?.userId}).</DialogDescription>
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

        {/* Cataract Result Dialog */}
        <Dialog open={isCataractModalOpen} onOpenChange={setIsCataractModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Cataract Screening Result</DialogTitle>
              <DialogDescription>
                AI cataract severity classification (account #{sessionUser?.userId}).
              </DialogDescription>
            </DialogHeader>

            {cataractResult ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">Severity</span>
                  <Badge>{cataractResult.prediction_label}</Badge>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">Confidence</span>
                  <span className="font-semibold">
                    {Math.round(cataractResult.confidence * 100)}%
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">P(cataract)</span>
                  <span className="font-semibold">
                    {Math.round(cataractResult.p_cataract * 100)}%
                  </span>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-sm text-muted-foreground mb-2">Probabilities per class</p>
                  <ul className="space-y-1 text-xs">
                    {Object.entries(cataractResult.probabilities).map(([label, prob]) => (
                      <li key={label} className="flex justify-between">
                        <span className="capitalize">{label}</span>
                        <span className="font-mono">{(prob * 100).toFixed(1)}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
                {cataractResult.heatmapBase64 ? (
                  <div className="rounded-lg border p-2">
                    <p className="text-sm text-muted-foreground mb-2">Grad-CAM Heatmap</p>
                    <img
                      src={`data:image/jpeg;base64,${cataractResult.heatmapBase64}`}
                      alt="Cataract Grad-CAM"
                      className="w-full h-48 object-cover rounded"
                    />
                  </div>
                ) : null}
              </div>
            ) : null}

            <DialogFooter>
              <Button onClick={() => setIsCataractModalOpen(false)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Non-Invasive Screening</h1>
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

          {/* Cataract Image — MobileNet inference */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Eye className="h-5 w-5 text-health-success" />
                Cataract Image
              </CardTitle>
              <CardDescription>Upload and run cataract severity inference</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col justify-center gap-4">
              <form className="space-y-3" onSubmit={onCataractSubmit}>
                <Input
                  type="file"
                  accept="image/*"
                  onChange={onEyeFileChange}
                  required
                />
                {eyePreviewUrl ? (
                  <div className="rounded-lg border p-2">
                    <img
                      src={eyePreviewUrl}
                      alt="Eye preview"
                      className="h-36 w-full rounded object-cover"
                    />
                  </div>
                ) : null}

                {eyeError ? (
                  <p className="flex items-start gap-2 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 mt-0.5" />
                    {eyeError}
                  </p>
                ) : null}

                <Button type="submit" className="w-full" disabled={eyeLoading}>
                  {eyeLoading ? 'Analyzing...' : 'Run Cataract Screening'}
                </Button>
              </form>

              <Button variant="outline" className="w-full" asChild>
                <a href="/dashboard/screening/cataract">Advanced Detection →</a>
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
                <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
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
    </RoleGuard>
  )
}
