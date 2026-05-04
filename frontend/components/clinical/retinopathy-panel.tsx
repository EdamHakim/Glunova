'use client'

import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { Eye, Info, Loader2, Sparkles, Upload } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { getApiUrls } from '@/lib/auth'
import { useAuth } from '@/components/auth-context'

const GRADE_NAMES = ['Mild', 'Moderate', 'Severe', 'Proliferative'] as const

const LESION_HINTS: Record<string, { primary: string[]; rule?: string }> = {
  'Mild NPDR': {
    primary: [
      'Microaneurysms (tiny red dots, < 125 µm) — usually scattered in the posterior pole',
    ],
  },
  'Moderate NPDR': {
    primary: [
      'Microaneurysms + dot/blot hemorrhages (deeper, intraretinal)',
      'Hard exudates (yellow, lipid deposits — often clustered around leaks)',
      'Cotton-wool spots (white, fluffy — nerve fiber layer infarcts)',
    ],
  },
  'Severe NPDR': {
    primary: [
      'Extensive intraretinal hemorrhages',
      'Venous beading (sausage-like vein irregularities)',
      'IRMA — Intraretinal microvascular abnormalities (shunt vessels)',
    ],
    rule: '4-2-1 rule (ETDRS): ≥20 hemorrhages in all 4 quadrants OR venous beading in ≥2 quadrants OR IRMA in ≥1 quadrant',
  },
  'Proliferative DR': {
    primary: [
      'Neovascularization at the disc (NVD) or elsewhere (NVE)',
      'Preretinal or vitreous hemorrhage',
      'Fibrovascular proliferation, possible tractional retinal detachment',
    ],
    rule: 'PDR is a sight-threatening emergency — refer for pan-retinal photocoagulation or anti-VEGF without delay (AAO PPP 2019).',
  },
}

type V51Detail = {
  dr_detected: boolean
  dr_probability: number
  no_dr_probability: number
  threshold_used: number
  confidence: number
  model_name: string
  model_version: string
}

type V8Detail = {
  grade_idx: number
  grade_label: string
  confidence: number
  probabilities: Record<string, number>
  model_name: string
  model_version: string
}

type InferResult = {
  patient_id: number
  clinical_grade: number
  clinical_grade_label: string
  v51: V51Detail
  v8: V8Detail | null
}

type GradcamResult = {
  method: string
  heatmap_base64: string
  grade_label: string
  confidence: number
  attention_area: number
}

function gradeBadgeClass(grade: number): string {
  // ICDR scale: 0=No DR (success), 1=Mild (info), 2=Moderate (warning), 3=Severe (danger), 4=PDR (destructive).
  switch (grade) {
    case 0:
      return 'bg-health-success/15 text-health-success border-health-success/30'
    case 1:
      return 'bg-health-info/15 text-health-info border-health-info/30'
    case 2:
      return 'bg-health-warning/15 text-health-warning border-health-warning/30'
    case 3:
      return 'bg-health-danger/15 text-health-danger border-health-danger/30'
    case 4:
      return 'bg-destructive/15 text-destructive border-destructive/30'
    default:
      return 'bg-muted text-muted-foreground border-border'
  }
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function RetinopathyPanel() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loadingInfer, setLoadingInfer] = useState(false)
  const [loadingGradcam, setLoadingGradcam] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<InferResult | null>(null)
  const [heatmap, setHeatmap] = useState<GradcamResult | null>(null)

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
    setHeatmap(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)
    setHeatmap(null)

    const pid = Number.parseInt(patientId.trim(), 10)
    if (!Number.isFinite(pid) || pid <= 0) return setError('Enter a valid patient ID.')
    if (!file) return setError('Select a fundus image.')
    if (!sessionUser || sessionUser.role !== 'doctor') {
      return setError('This tool is only available to doctors.')
    }

    setLoadingInfer(true)
    try {
      const { fastapi } = getApiUrls()
      const form = new FormData()
      form.append('patient_id', String(pid))
      form.append('image', file)

      const res = await fetch(`${fastapi}/clinic/retinopathy/infer`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(typeof body?.detail === 'string' ? body.detail : 'Retinopathy analysis failed.')
      }
      const data = await res.json()
      setResult({
        patient_id: data.patient_id,
        clinical_grade: data.clinical_grade,
        clinical_grade_label: data.clinical_grade_label,
        v51: data.v51,
        v8: data.v8,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.')
    } finally {
      setLoadingInfer(false)
    }
  }

  async function onGenerateHeatmap() {
    if (!file || !result) return
    setError('')
    const pid = Number.parseInt(patientId.trim(), 10)
    if (!Number.isFinite(pid) || pid <= 0) return setError('Enter a valid patient ID.')
    setLoadingGradcam(true)
    try {
      const { fastapi } = getApiUrls()
      const form = new FormData()
      form.append('patient_id', String(pid))
      form.append('image', file)
      const res = await fetch(`${fastapi}/clinic/retinopathy/gradcam`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(typeof body?.detail === 'string' ? body.detail : 'Heatmap generation failed.')
      }
      const data = await res.json()
      setHeatmap({
        method: data.method,
        heatmap_base64: data.heatmap_base64,
        grade_label: data.grade_label,
        confidence: data.confidence,
        attention_area: data.attention_area,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Heatmap request failed.')
    } finally {
      setLoadingGradcam(false)
    }
  }

  if (sessionLoading || sessionUser?.role !== 'doctor') return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Eye className="h-5 w-5 text-primary" />
          Diabetic retinopathy detection
        </CardTitle>
        <CardDescription>
          Upload a fundus image to detect diabetic retinopathy and grade its severity (0–4 ICDR scale).
          Generate an attention map to see which retinal areas the model used for its decision.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4 max-w-3xl">
          <div className="space-y-2 max-w-xs">
            <Label htmlFor="dr-patient-id">Patient ID</Label>
            <Input
              id="dr-patient-id"
              type="number"
              min={1}
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dr-image">Fundus image</Label>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input
                id="dr-image"
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

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={loadingInfer || loadingGradcam}>
              {loadingInfer ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Run analysis
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!result || loadingInfer || loadingGradcam}
              onClick={() => {
                void onGenerateHeatmap()
              }}
            >
              {loadingGradcam ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating heatmap...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate heatmap
                </>
              )}
            </Button>
          </div>
        </form>

        {result ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-lg border p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-muted-foreground">Clinical grade (ICDR)</span>
                <Badge variant="outline" className={`text-base px-3 py-1 ${gradeBadgeClass(result.clinical_grade)}`}>
                  {result.clinical_grade} — {result.clinical_grade_label}
                </Badge>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2 rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Step 1 — DR Detection</span>
                  <Badge variant={result.v51.dr_detected ? 'destructive' : 'secondary'}>
                    {result.v51.dr_detected ? 'DR detected' : 'No DR'}
                  </Badge>
                </div>
                <p className="text-sm">DR prob: <span className="font-mono font-semibold">{pct(result.v51.dr_probability)}</span></p>
                <p className="text-sm">No DR prob: <span className="font-mono">{pct(result.v51.no_dr_probability)}</span></p>
              </div>

              {result.v8 ? (
                <div className="space-y-3 rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Step 2 — Severity Grading</span>
                    <Badge variant="outline">
                      {result.v8.grade_label} · {pct(result.v8.confidence)}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    {GRADE_NAMES.map((label) => {
                      const p = result.v8?.probabilities[label] ?? 0
                      const isWinner = label === result.v8?.grade_label
                      return (
                        <div key={label} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className={isWinner ? 'font-semibold' : 'text-muted-foreground'}>{label}</span>
                            <span className="font-mono">{pct(p)}</span>
                          </div>
                          <Progress value={p * 100} className="h-2" />
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border p-3 bg-muted/30">
                  <p className="text-sm text-muted-foreground">
                    Severity grading was skipped because no DR was detected.
                  </p>
                </div>
              )}
            </div>

            {heatmap ? (
              <div className="rounded-lg border p-3 space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-medium flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4 text-primary" />
                      XAI (Grad-CAM)
                    </p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
                      Gradient-weighted Class Activation Mapping highlights the retinal regions that
                      most influenced the model&apos;s severity grading. Use it as an interpretability
                      check — not as a replacement for fundoscopy.
                    </p>
                  </div>
                  <Badge variant="outline" className="shrink-0">
                    {heatmap.grade_label}
                  </Badge>
                </div>

                <img
                  src={`data:image/jpeg;base64,${heatmap.heatmap_base64}`}
                  alt="Retinopathy AI attention overlay"
                  className="w-full max-h-[420px] object-contain rounded bg-muted"
                />

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-md border bg-muted/30 p-3">
                    <p className="text-xs font-semibold mb-2 flex items-center gap-1.5">
                      <Info className="h-3.5 w-3.5" />
                      Heatmap legend
                    </p>
                    <ul className="space-y-1.5 text-xs">
                      <li className="flex items-center gap-2">
                        <span className="inline-block h-3 w-3 rounded-full bg-red-500" />
                        <span><strong>Red / orange</strong> — strongest model attention (decisive lesion)</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="inline-block h-3 w-3 rounded-full bg-yellow-400" />
                        <span><strong>Yellow / green</strong> — moderate contribution</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="inline-block h-3 w-3 rounded-full bg-blue-500" />
                        <span><strong>Blue / dark</strong> — region ignored by the model</span>
                      </li>
                    </ul>
                  </div>

                  <div className="rounded-md border bg-muted/30 p-3">
                    <p className="text-xs font-semibold mb-2">
                      Lesions to verify for {heatmap.grade_label}
                    </p>
                    {LESION_HINTS[heatmap.grade_label] ? (
                      <>
                        <ul className="space-y-1 text-xs text-muted-foreground list-disc pl-4">
                          {LESION_HINTS[heatmap.grade_label].primary.map((lesion) => (
                            <li key={lesion}>{lesion}</li>
                          ))}
                        </ul>
                        {LESION_HINTS[heatmap.grade_label].rule ? (
                          <p className="text-xs mt-2 pt-2 border-t border-border/60 text-foreground/90">
                            <strong>Reference:</strong> {LESION_HINTS[heatmap.grade_label].rule}
                          </p>
                        ) : null}
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        No specific lesion checklist for this grade.
                      </p>
                    )}
                  </div>
                </div>

              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
