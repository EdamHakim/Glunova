'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { AlertTriangle, Image as ImageIcon } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import RoleGuard from '@/components/auth/role-guard'

function PanelLoading({ label }: { label: string }) {
  return (
    <div className="flex min-h-[160px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
      Loading {label}…
    </div>
  )
}

const DFUSegmentationPanel = dynamic(
  () => import('@/components/clinical/dfu-segmentation-panel').then((m) => ({ default: m.DFUSegmentationPanel })),
  { loading: () => <PanelLoading label="DFU tools" />, ssr: false },
)
const RetinopathyPanel = dynamic(
  () => import('@/components/clinical/retinopathy-panel').then((m) => ({ default: m.RetinopathyPanel })),
  { loading: () => <PanelLoading label="retinopathy tools" />, ssr: false },
)
const ThermalFootPanel = dynamic(
  () => import('@/components/clinical/thermal-foot-panel').then((m) => ({ default: m.ThermalFootPanel })),
  { loading: () => <PanelLoading label="thermal imaging" />, ssr: false },
)
import {
  getClinicalSummary,
  listClinicalPriorities,
  listImagingQueue,
  type ClinicalPriorityRow,
  type ImagingQueueRow,
} from '@/lib/clinical-api'

export default function ClinicalPage() {
  const t = useTranslations('clinical')
  const [summary, setSummary] = useState({ critical_cases: 0, high_risk: 0, stable: 0, pending_review: 0 })
  const [priorities, setPriorities] = useState<ClinicalPriorityRow[]>([])
  const [imagingQueue, setImagingQueue] = useState<ImagingQueueRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all([getClinicalSummary(), listClinicalPriorities(), listImagingQueue()])
      .then(([summaryPayload, prioritiesPayload, imagingPayload]) => {
        if (cancelled) return
        setSummary(summaryPayload)
        setPriorities(prioritiesPayload.items)
        setImagingQueue(imagingPayload.items)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load clinical data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <RoleGuard
      allowedRoles={['doctor']}
      title={t('unavailableTitle')}
      description={t('unavailableDesc')}
    >
      <div className="space-y-6 p-4 sm:p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('decisionSupportTitle')}</h1>
          <p className="text-muted-foreground mt-2">{t('decisionSupportDesc')}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('criticalCases')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-destructive">{summary.critical_cases}</div>
              <p className="text-xs text-destructive flex items-center gap-1 mt-1">
                <AlertTriangle className="h-3 w-3" /> {t('criticalCasesDesc')}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('highRisk')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-health-danger">{summary.high_risk}</div>
              <p className="text-xs text-health-danger mt-1">{t('highRiskDesc')}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('stablePatients')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-health-success">{summary.stable}</div>
              <p className="text-xs text-health-success mt-1">{t('stableDesc')}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('pendingReview')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-primary">{summary.pending_review}</div>
              <p className="text-xs text-muted-foreground mt-1">{t('pendingReviewDesc')}</p>
            </CardContent>
          </Card>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
        {loading && <p className="text-sm text-muted-foreground">{t('loadingInsights')}</p>}

        <ThermalFootPanel />
        <RetinopathyPanel />
        <DFUSegmentationPanel />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t('patientPrioritization')}
            </CardTitle>
            <CardDescription>{t('aiRankedByUrgency')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {priorities.map((patient, idx) => (
                <div
                  key={patient.id}
                  className={`p-4 border rounded-lg hover:bg-muted/50 transition-colors ${
                    patient.priority === 'urgent' ? 'border-destructive/50 bg-destructive/5' :
                    patient.priority === 'high' ? 'border-health-danger/50 bg-health-danger/5' :
                    'border-border'
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-4 sm:flex-1">
                      <div className="shrink-0">
                        <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center font-bold">
                          {idx + 1}
                        </div>
                      </div>
                      <div className="flex-1">
                        <p className="font-medium">{patient.patient_name}</p>
                        <p className="text-sm text-muted-foreground mt-0.5">{patient.summary}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                      <div className="sm:text-right">
                        <Badge
                          className={
                            patient.priority === 'urgent' ? 'bg-destructive/10 text-destructive border-destructive/20' :
                            patient.priority === 'high' ? 'bg-health-danger/10 text-health-danger border-health-danger/20' :
                            patient.priority === 'medium' ? 'bg-health-warning/10 text-health-warning border-health-warning/20' :
                            'bg-health-success/10 text-health-success border-health-success/20'
                          }
                          variant="outline"
                        >
                          {patient.priority}
                        </Badge>
                        <p className="text-xs text-muted-foreground mt-2">{new Date(patient.created_at).toLocaleString()}</p>
                      </div>
                      <Button variant="outline" size="sm">{t('review')}</Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              {t('imagingQueue')}
            </CardTitle>
            <CardDescription>{t('imagingQueueDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {imagingQueue.map((row) => (
                <div key={row.id} className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                  <div className="aspect-square bg-muted rounded-lg mb-3 flex items-center justify-center">
                    <ImageIcon className="h-12 w-12 text-muted-foreground" />
                  </div>
                  <p className="font-medium text-sm">{row.analysis_type.replace('_', ' ')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{row.patient_name} • {new Date(row.captured_at).toLocaleString()}</p>
                  <div className="mt-3 flex gap-2">
                    <Badge variant="outline" className="bg-health-warning/10 text-health-warning border-health-warning/20">
                      {t('pendingLabel')}
                    </Badge>
                    <Badge variant="outline">{t('severityLabel')} {row.severity_grade}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}
