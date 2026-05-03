'use client'

import { useMemo, useState } from 'react'
import type { ChangeEvent, FormEvent, ReactNode } from 'react'
import { AlertCircle, Eye, Mic, ScanSearch } from 'lucide-react'
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
import { useAuth } from '@/components/auth-context'

type TongueResult = {
  probability: number
  prediction_label: string
  threshold_used: number
  heatmapBase64?: string
}

type CataractResult = {
  prediction_index: number
  prediction_label: string
  confidence: number
  p_cataract: number
  probabilities: Record<string, number>
  heatmapBase64?: string
}

type ScreeningKind = 'tongue' | 'cataract'

export default function ScreeningPage() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()

  const [tongueFile, setTongueFile] = useState<File | null>(null)
  const [tonguePreviewUrl, setTonguePreviewUrl] = useState('')
  const [tongueLoading, setTongueLoading] = useState(false)
  const [tongueResult, setTongueResult] = useState<TongueResult | null>(null)

  const [cataractFile, setCataractFile] = useState<File | null>(null)
  const [cataractPreviewUrl, setCataractPreviewUrl] = useState('')
  const [cataractLoading, setCataractLoading] = useState(false)
  const [cataractResult, setCataractResult] = useState<CataractResult | null>(null)

  const [error, setError] = useState('')
  const [activeModal, setActiveModal] = useState<ScreeningKind | null>(null)

  const riskPercent = useMemo(() => {
    const scores = [
      tongueResult ? tongueResult.probability : 0,
      cataractResult ? cataractResult.p_cataract : 0,
    ]
    return Math.round(Math.max(...scores) * 100)
  }, [tongueResult, cataractResult])

  function validateSession() {
    if (!sessionUser) {
      throw new Error('You must login first.')
    }
    if (sessionUser.role !== 'patient' || sessionUser.userId == null) {
      throw new Error('Screening is only available to patient accounts with a valid session.')
    }
  }

  function onTongueFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setTongueFile(selected)
    setTongueResult(null)
    setError('')
    setTonguePreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  function onCataractFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setCataractFile(selected)
    setCataractResult(null)
    setError('')
    setCataractPreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  async function postImage(endpoint: string, file: File) {
    const { fastapi } = getApiUrls()
    const payload = new FormData()
    payload.append('image', file)

    const response = await fetch(`${fastapi}${endpoint}`, {
      method: 'POST',
      credentials: 'include',
      body: payload,
    })

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data?.detail ?? 'Screening request failed.')
    }

    return response.json()
  }

  async function onTongueSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setTongueResult(null)

    if (!tongueFile) {
      setError('Please select a tongue image before submitting.')
      return
    }

    setTongueLoading(true)
    try {
      validateSession()
      const data = await postImage('/screening/tongue/infer', tongueFile)
      const result: TongueResult = {
        probability: data.probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
      }

      const gradcamData = await postImage('/screening/tongue/gradcam', tongueFile).catch(() => null)
      if (gradcamData?.heatmap_base64) {
        result.heatmapBase64 = gradcamData.heatmap_base64
      }

      setTongueResult(result)
      setActiveModal('tongue')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setTongueLoading(false)
    }
  }

  async function onCataractSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setCataractResult(null)

    if (!cataractFile) {
      setError('Please select an eye image before submitting.')
      return
    }

    setCataractLoading(true)
    try {
      validateSession()
      const data = await postImage('/screening/cataract/infer', cataractFile)
      const result: CataractResult = {
        prediction_index: data.prediction_index,
        prediction_label: data.prediction_label,
        confidence: data.confidence,
        p_cataract: data.p_cataract,
        probabilities: data.probabilities,
      }

      const gradcamData = await postImage('/screening/cataract/gradcam', cataractFile).catch(() => null)
      if (gradcamData?.heatmap_base64) {
        result.heatmapBase64 = gradcamData.heatmap_base64
      }

      setCataractResult(result)
      setActiveModal('cataract')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setCataractLoading(false)
    }
  }

  if (sessionLoading) {
    return (
      <div className="space-y-6 p-4 sm:p-6">
        <p className="text-sm text-muted-foreground">Loading session...</p>
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
        <Dialog open={activeModal !== null} onOpenChange={(open) => setActiveModal(open ? activeModal : null)}>
          <DialogContent className="sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>{activeModal === 'cataract' ? 'Cataract Screening Result' : 'Tongue Screening Result'}</DialogTitle>
              <DialogDescription>AI prediction for your screening account #{sessionUser?.userId}.</DialogDescription>
            </DialogHeader>

            {activeModal === 'tongue' && tongueResult ? (
              <div className="space-y-3">
                <ResultRow label="Prediction" value={<Badge>{tongueResult.prediction_label}</Badge>} />
                <ResultRow label="Probability" value={`${Math.round(tongueResult.probability * 100)}%`} />
                <ResultRow label="Threshold Used" value={String(tongueResult.threshold_used)} />
                <HeatmapImage base64={tongueResult.heatmapBase64} alt="Tongue Grad-CAM" />
              </div>
            ) : null}

            {activeModal === 'cataract' && cataractResult ? (
              <div className="space-y-3">
                <ResultRow label="Grade" value={<Badge>{cataractResult.prediction_label}</Badge>} />
                <ResultRow label="Confidence" value={`${Math.round(cataractResult.confidence * 100)}%`} />
                <ResultRow label="Cataract Signal" value={`${Math.round(cataractResult.p_cataract * 100)}%`} />
                <div className="rounded-lg border p-3">
                  <p className="mb-2 text-sm text-muted-foreground">Class Probabilities</p>
                  <div className="space-y-2">
                    {Object.entries(cataractResult.probabilities).map(([label, value]) => (
                      <ProbabilityBar key={label} label={label} value={value} />
                    ))}
                  </div>
                </div>
                <HeatmapImage base64={cataractResult.heatmapBase64} alt="Cataract Grad-CAM" />
              </div>
            ) : null}

            <DialogFooter>
              <Button onClick={() => setActiveModal(null)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Non-Invasive Screening</h1>
          <p className="mt-2 text-muted-foreground">AI-powered health assessment using voice, tongue, and eye imaging</p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Mic className="h-5 w-5 text-health-info" />
                Voice Recording
              </CardTitle>
              <CardDescription>Record patient voice sample</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col justify-center gap-4">
              <div className="flex aspect-video items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted">
                <div className="text-center">
                  <Mic className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Click to record</p>
                </div>
              </div>
              <Button variant="outline" className="w-full">
                Start Recording
              </Button>
            </CardContent>
          </Card>

          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <ScanSearch className="h-5 w-5 text-health-warning" />
                Tongue Image
              </CardTitle>
              <CardDescription>Upload and run PyTorch tongue diabetes inference</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col justify-center gap-4">
              <form className="space-y-3" onSubmit={onTongueSubmit}>
                <Input type="file" accept="image/*" onChange={onTongueFileChange} required />
                <PreviewImage src={tonguePreviewUrl} alt="Tongue preview" />
                <Button type="submit" className="w-full" disabled={tongueLoading}>
                  {tongueLoading ? 'Analyzing...' : 'Run Tongue Screening'}
                </Button>
              </form>
            </CardContent>
          </Card>

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
                <Input type="file" accept="image/*" onChange={onCataractFileChange} required />
                <PreviewImage src={cataractPreviewUrl} alt="Eye preview" />
                <Button type="submit" className="w-full" disabled={cataractLoading}>
                  {cataractLoading ? 'Analyzing...' : 'Run Cataract Screening'}
                </Button>
              </form>
              <Button variant="outline" className="w-full" asChild>
                <a href="/dashboard/screening/cataract">Advanced Detection →</a>
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>AI Assessment Results</CardTitle>
            <CardDescription>Predictions from multi-modal analysis</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="rounded-lg border border-border p-4">
                <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <span className="font-medium">Highest Current Signal</span>
                  <Badge className="px-3 py-1 text-lg">{riskPercent}%</Badge>
                </div>
                <div className="h-2 w-full rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-linear-to-r from-health-success via-health-warning to-health-danger"
                    style={{ width: `${riskPercent}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  Results are saved into monitoring after each successful screening.
                </p>
              </div>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <SummaryTile title="Voice Analysis" value="Not configured" detail="Voice model is not connected yet." />
                <SummaryTile
                  title="Tongue Examination"
                  value={tongueResult ? `${tongueResult.prediction_label} (${Math.round(tongueResult.probability * 100)}%)` : 'No result'}
                  detail={tongueResult ? `Threshold ${tongueResult.threshold_used}` : 'Submit a tongue image.'}
                  onDetails={tongueResult ? () => setActiveModal('tongue') : undefined}
                />
                <SummaryTile
                  title="Cataract Examination"
                  value={cataractResult ? `${cataractResult.prediction_label} (${Math.round(cataractResult.confidence * 100)}%)` : 'No result'}
                  detail={cataractResult ? `Signal ${Math.round(cataractResult.p_cataract * 100)}%` : 'Submit an eye image.'}
                  onDetails={cataractResult ? () => setActiveModal('cataract') : undefined}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              AI Explainability
            </CardTitle>
            <CardDescription>Grad-CAM visualizations of predictions</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <ExplainabilityPanel title="Voice Features" emptyText="Voice explainability is not configured yet." />
              <ExplainabilityPanel
                title="Tongue Image"
                base64={tongueResult?.heatmapBase64}
                alt="Tongue Grad-CAM heatmap"
                emptyText="Run tongue screening to generate a heatmap."
              />
              <ExplainabilityPanel
                title="Cataract Image"
                base64={cataractResult?.heatmapBase64}
                alt="Cataract Grad-CAM heatmap"
                emptyText="Run cataract screening to generate a heatmap."
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}

function ResultRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  )
}

function PreviewImage({ src, alt }: { src: string; alt: string }) {
  if (!src) return null
  return (
    <div className="rounded-lg border p-2">
      <img src={src} alt={alt} className="h-36 w-full rounded object-cover" />
    </div>
  )
}

function HeatmapImage({ base64, alt }: { base64?: string; alt: string }) {
  if (!base64) return null
  return (
    <div className="rounded-lg border p-2">
      <p className="mb-2 text-sm text-muted-foreground">Grad-CAM Heatmap</p>
      <img src={`data:image/jpeg;base64,${base64}`} alt={alt} className="h-48 w-full rounded object-cover" />
    </div>
  )
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="capitalize text-muted-foreground">{label}</span>
        <span className="font-medium">{Math.round(value * 100)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  )
}

function SummaryTile({
  title,
  value,
  detail,
  onDetails,
}: {
  title: string
  value: string
  detail: string
  onDetails?: () => void
}) {
  return (
    <div className="rounded-lg bg-muted p-3">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 font-semibold">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      {onDetails ? (
        <Button variant="link" className="mt-1 h-auto px-0" onClick={onDetails}>
          View details
        </Button>
      ) : null}
    </div>
  )
}

function ExplainabilityPanel({
  title,
  base64,
  alt,
  emptyText,
}: {
  title: string
  base64?: string
  alt?: string
  emptyText: string
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{title}</p>
      {base64 ? (
        <div className="aspect-square rounded-lg bg-muted p-2">
          <img src={`data:image/jpeg;base64,${base64}`} alt={alt ?? title} className="h-full w-full rounded object-cover" />
        </div>
      ) : (
        <div className="flex aspect-square items-center justify-center rounded-lg bg-muted p-3">
          <p className="text-center text-xs text-muted-foreground">{emptyText}</p>
        </div>
      )}
    </div>
  )
}
