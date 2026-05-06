'use client'

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
} from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  Layers,
  Loader2,
  Ruler,
  ScanSearch,
  Target,
  Upload,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { getApiUrls } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { useAuth } from '@/components/auth-context'

type DFUSeverity = 'none' | 'mild' | 'moderate' | 'severe' | 'critical'

type DFUResult = {
  patient_id: number
  ulcer_detected: boolean
  ulcer_severity: DFUSeverity
  ulcer_area_ratio: number
  ulcer_area_px: number
  ulcer_area_mm2: number
  bbox_width_mm: number
  bbox_height_mm: number
  mm_per_pixel: number
  threshold_used: number
  overlay_base64: string
  used_auto_threshold: boolean
  used_auto_mm_pixel: boolean
}

function formatAreaMm2(mm2: number): string {
  if (!Number.isFinite(mm2)) return '—'
  if (mm2 >= 100) {
    const cm = mm2 / 100
    return `${Math.round(mm2).toLocaleString()} mm² (${cm.toFixed(2)} cm²)`
  }
  return `${mm2.toFixed(2)} mm²`
}

function resultHeroSurface(result: DFUResult): string {
  if (!result.ulcer_detected) {
    return 'border-emerald-500/30 bg-emerald-500/[0.07] dark:bg-emerald-950/40'
  }
  switch (result.ulcer_severity) {
    case 'critical':
    case 'severe':
      return 'border-destructive/45 bg-destructive/[0.07] dark:bg-destructive/15'
    case 'moderate':
      return 'border-amber-500/40 bg-amber-500/[0.08] dark:bg-amber-950/35'
    case 'mild':
      return 'border-sky-500/35 bg-sky-500/[0.06] dark:bg-sky-950/30'
    default:
      return 'border-border bg-muted/50'
  }
}

function MetricTile({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: ComponentType<{ className?: string }>
  label: string
  value: ReactNode
  hint?: string
}) {
  return (
    <div className="rounded-xl border bg-card/60 p-3 shadow-xs backdrop-blur-sm transition-colors hover:bg-card/80">
      <div className="flex gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
          <Icon className="h-4 w-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <div className="text-base font-semibold tabular-nums leading-snug">{value}</div>
          {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
      </div>
    </div>
  )
}

export function DFUSegmentationPanel() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [mmPerPixel, setMmPerPixel] = useState('0.5')
  const [threshold, setThreshold] = useState('0.5')
  const [thresholdAuto, setThresholdAuto] = useState(true)
  const [mmPerPixelAuto, setMmPerPixelAuto] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DFUResult | null>(null)

  const areaPercent = useMemo(() => (result ? Math.round(result.ulcer_area_ratio * 100) : 0), [result])

  function severityBadge(severity: DFUSeverity) {
    const label =
      severity === 'none'
        ? 'None'
        : severity.charAt(0).toUpperCase() + severity.slice(1)
    switch (severity) {
      case 'critical':
      case 'severe':
        return (
          <Badge variant="destructive" className="capitalize">
            {label}
          </Badge>
        )
      case 'moderate':
        return (
          <Badge
            variant="outline"
            className="capitalize border-amber-600/70 bg-amber-500/15 text-amber-950 dark:text-amber-200"
          >
            {label}
          </Badge>
        )
      case 'mild':
        return (
          <Badge variant="secondary" className="capitalize">
            {label}
          </Badge>
        )
      default:
        return (
          <Badge variant="outline" className="text-muted-foreground capitalize">
            {label}
          </Badge>
        )
    }
  }

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
    if (!mmPerPixelAuto && (!Number.isFinite(mm) || mm <= 0)) return setError('mm/pixel must be > 0 (or enable auto estimate).')
    if (!thresholdAuto && (!Number.isFinite(thr) || thr < 0 || thr > 1))
      return setError('Threshold must be between 0 and 1 (or enable automatic threshold).')
    if (!file) return setError('Select a foot ulcer image.')
    if (!sessionUser || sessionUser.role !== 'doctor') return setError('This tool is only available to doctors.')

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const form = new FormData()
      form.append('patient_id', String(pid))
      form.append('image', file)
      form.append('threshold_auto', thresholdAuto ? 'true' : 'false')
      form.append('mm_per_pixel_auto', mmPerPixelAuto ? 'true' : 'false')
      form.append('threshold', thresholdAuto ? '0.5' : String(thr))
      form.append('mm_per_pixel', mmPerPixelAuto ? '0.5' : String(mm))

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
        ulcer_severity: (data.ulcer_severity ?? 'none') as DFUSeverity,
        ulcer_area_ratio: data.ulcer_area_ratio,
        ulcer_area_px: data.ulcer_area_px,
        ulcer_area_mm2: data.ulcer_area_mm2,
        bbox_width_mm: data.bbox_width_mm,
        bbox_height_mm: data.bbox_height_mm,
        mm_per_pixel: data.mm_per_pixel,
        threshold_used: data.threshold_used,
        overlay_base64: data.overlay_base64,
        used_auto_threshold: thresholdAuto,
        used_auto_mm_pixel: mmPerPixelAuto,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.')
    } finally {
      setLoading(false)
    }
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
          dimensions, and view the XAI overlay on screen.
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
              <Input
                id="dfu-mm-px"
                type="number"
                step="0.01"
                min="0.01"
                value={mmPerPixel}
                onChange={(e) => setMmPerPixel(e.target.value)}
                disabled={mmPerPixelAuto}
              />
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox
                  checked={mmPerPixelAuto}
                  onCheckedChange={(v) => setMmPerPixelAuto(v === true)}
                  id="dfu-mm-auto"
                />
                <span id="dfu-mm-auto-desc">
                  Estimate from image (~24&nbsp;cm along longest edge — rough only; use ruler when possible).
                </span>
              </label>
            </div>
            <div className="space-y-2">
              <Label htmlFor="dfu-threshold">Threshold (0-1)</Label>
              <Input
                id="dfu-threshold"
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                disabled={thresholdAuto}
              />
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox
                  checked={thresholdAuto}
                  onCheckedChange={(v) => setThresholdAuto(v === true)}
                  id="dfu-thresh-auto"
                />
                <span>Automatic threshold from model probabilities</span>
              </label>
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
          </div>
        </form>

        {result ? (
          <div className="mt-8 space-y-6">
            <Separator className="max-w-5xl" />
            <div className="space-y-2 max-w-5xl">
              <h3 className="text-sm font-semibold tracking-tight text-foreground">Analysis results</h3>
              <p className="text-xs text-muted-foreground">
                Patient #{result.patient_id} · model output for decision support only
              </p>
            </div>

            <div
              className={cn(
                'max-w-5xl rounded-2xl border-2 p-4 sm:p-5',
                resultHeroSurface(result),
              )}
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex gap-3">
                  <div
                    className={cn(
                      'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border bg-background/80 shadow-sm',
                      result.ulcer_detected
                        ? 'text-amber-900 dark:text-amber-100'
                        : 'text-emerald-700 dark:text-emerald-400',
                    )}
                  >
                    {result.ulcer_detected ? (
                      <AlertTriangle className="h-6 w-6" aria-hidden />
                    ) : (
                      <CheckCircle2 className="h-6 w-6" aria-hidden />
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-lg font-semibold leading-tight sm:text-xl">
                      {result.ulcer_detected ? 'Possible ulcer region on mask' : 'No ulcer-like region on mask'}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {result.ulcer_detected
                        ? 'Review overlay and correlate with the clinical exam.'
                        : 'Negative segmentation does not rule out early or non-visible lesions.'}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                  <Badge
                    variant={result.ulcer_detected ? 'destructive' : 'secondary'}
                    className="px-3 py-1 text-xs font-medium"
                  >
                    {result.ulcer_detected ? 'Positive mask' : 'Negative mask'}
                  </Badge>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      AI severity
                    </span>
                    {severityBadge(result.ulcer_severity)}
                  </div>
                </div>
              </div>

              {result.ulcer_detected ? (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Mask vs. full image</span>
                    <span className="tabular-nums font-medium text-foreground">{areaPercent}%</span>
                  </div>
                  <div
                    className="h-2.5 overflow-hidden rounded-full bg-background/60 ring-1 ring-inset ring-black/5 dark:ring-white/10"
                    role="progressbar"
                    aria-valuenow={Math.min(100, areaPercent)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Ulcer mask coverage as percent of image"
                  >
                    <div
                      className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                      style={{ width: `${Math.min(100, Math.max(0, areaPercent))}%` }}
                    />
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid max-w-5xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricTile
                icon={Target}
                label="Ulcer area"
                value={
                  result.ulcer_detected ? formatAreaMm2(result.ulcer_area_mm2) : '—'
                }
                hint={
                  result.ulcer_detected
                    ? `${result.ulcer_area_px.toLocaleString()} px in model space`
                    : undefined
                }
              />
              <MetricTile
                icon={Layers}
                label="Bounding box"
                value={
                  result.ulcer_detected
                    ? `${result.bbox_width_mm.toFixed(1)} × ${result.bbox_height_mm.toFixed(1)} mm`
                    : '—'
                }
                hint={result.ulcer_detected ? 'Axis-aligned box around mask' : undefined}
              />
              <MetricTile
                icon={Ruler}
                label="Calibration"
                value={`${result.mm_per_pixel} mm/px`}
                hint={result.used_auto_mm_pixel ? 'Estimated from image (~24 cm prior)' : 'Manual mm/pixel'}
              />
              <MetricTile
                icon={ScanSearch}
                label="Mask threshold"
                value={result.threshold_used.toFixed(3)}
                hint={result.used_auto_threshold ? 'Chosen per image (auto)' : 'Manual value'}
              />
            </div>

            <div className="grid max-w-5xl gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:items-start lg:gap-8">
              <Alert className="border-muted-foreground/20 bg-muted/25">
                <Info className="size-4" aria-hidden />
                <AlertTitle>Severity & sizing</AlertTitle>
                <AlertDescription className="text-muted-foreground">
                  Severity is derived from segmented area in mm² ({!result.used_auto_mm_pixel ? 'manual' : 'approx.'}{' '}
                  calibration). It is <strong>not</strong> Wagner / University of Texas grading — use it only as triage
                  alongside your exam.
                </AlertDescription>
              </Alert>

              <div className="overflow-hidden rounded-2xl border bg-muted/20 shadow-sm ring-1 ring-black/5 dark:ring-white/10">
                <div className="flex items-center justify-between border-b bg-muted/40 px-4 py-2.5">
                  <span className="text-sm font-medium">Segmentation overlay</span>
                  <span className="text-[11px] tabular-nums text-muted-foreground">
                    Red channel · ulcer emphasis
                  </span>
                </div>
                <div className="relative flex min-h-[220px] items-center justify-center bg-linear-to-b from-muted/30 to-muted p-3 sm:min-h-[280px] lg:min-h-[320px]">
                  <img
                    src={`data:image/png;base64,${result.overlay_base64}`}
                    alt=""
                    className="max-h-[380px] w-full object-contain drop-shadow-md"
                  />
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
