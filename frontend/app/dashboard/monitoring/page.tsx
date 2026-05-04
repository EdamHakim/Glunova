'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  CheckCircle2,
  Clock,
  FileText,
  Info,
  Pill,
  ScanSearch,
  TrendingUp,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import './monitoring.css'

import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { listMedications, type PatientMedicationRow } from '@/lib/medications-api'
import {
  getDiseaseProgression,
  getRiskStratification,
  getScreeningHistory,
  listLabResults,
  listMonitoringAlerts,
  type DiseaseProgression,
  type MonitoringAlert,
  type PatientLabResultRow,
  type RiskStratification,
  type ScreeningModalitySummary,
} from '@/lib/monitoring-api'
import { DiseaseProgressionTracker } from '@/components/monitoring/disease-progression-tracker'
import { RiskStratificationCard } from '@/components/monitoring/risk-stratification-card'
import { ScreeningHistoryTab } from '@/components/monitoring/screening-history-tab'

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'critical':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    case 'warning':
      return 'bg-health-danger/10 text-health-danger border-health-danger/20'
    case 'info':
      return 'bg-health-warning/10 text-health-warning border-health-warning/20'
    default:
      return 'bg-health-success/10 text-health-success border-health-success/20'
  }
}

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

function getMedicationBadgeClass(status: string) {
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

export default function MonitoringPage() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [medications, setMedications] = useState<PatientMedicationRow[]>([])
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([])
  const [labResults, setLabResults] = useState<PatientLabResultRow[]>([])
  const [progression, setProgression] = useState<DiseaseProgression | null>(null)
  const [medicationError, setMedicationError] = useState<string | null>(null)
  const [monitoringError, setMonitoringError] = useState<string | null>(null)
  const [labLoading, setLabLoading] = useState(false)
  const [medicationLoading, setMedicationLoading] = useState(false)
  const [monitoringLoading, setMonitoringLoading] = useState(false)
  const [riskStrat, setRiskStrat] = useState<RiskStratification | null>(null)
  const [riskStratLoading, setRiskStratLoading] = useState(false)
  const [riskStratError, setRiskStratError] = useState<string | null>(null)
  const [screeningHistory, setScreeningHistory] = useState<ScreeningModalitySummary[]>([])
  const [screeningHistoryLoading, setScreeningHistoryLoading] = useState(false)
  const [screeningHistoryError, setScreeningHistoryError] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<{ url: string; filename: string } | null>(null)
  const [previewError, setPreviewError] = useState(false)

  // Reset preview error when modal opens with a new document
  useEffect(() => {
    setPreviewError(false)
  }, [selectedDoc])

  // Group lab results by document (used in the Lab Results accordion below).
  const labsByDocument = labResults.reduce((acc, lab) => {
    const docId = lab.source_document_id || 'manual'
    if (!acc[docId]) {
      acc[docId] = {
        id: docId,
        filename: lab.source_document_filename || 'Other Results',
        date: lab.source_document_created_at || lab.observed_at || lab.created_at,
        url: lab.source_document_url,
        preview_url: lab.source_document_preview_url,
        mime_type: lab.source_document_mime_type,
        results: [],
      }
    }
    acc[docId].results.push(lab)
    return acc
  }, {} as Record<string, { id: string; filename: string; date: string; url: string | null; preview_url: string | null; results: PatientLabResultRow[] }>)

  const labDocuments = Object.values(labsByDocument).sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
  )

  const isImage = (mime: string | null) => mime?.toLowerCase().startsWith('image/')
  const role = user?.role
  const isCaregiver = role === 'caregiver'
  const isDoctor = role === 'doctor'
  const intro = isDoctor
    ? 'Track assigned patient alerts, trends, and escalation signals.'
    : isCaregiver
      ? 'Follow linked patient updates, reminders, and high-level alerts.'
      : 'Track your health alerts, timeline, and progression over time.'

  useEffect(() => {
    if (user?.role === 'patient') {
      setPatientId(user.id)
    }
  }, [user])

  useEffect(() => {
    if (!patientId) {
      setMedications([])
      setAlerts([])
      setLabResults([])
      setProgression(null)
      return
    }

    let cancelled = false
    setMedicationLoading(true)
    setMedicationError(null)
    setLabLoading(true)
    setMonitoringLoading(true)
    setMonitoringError(null)
    void listMedications(patientId)
      .then((payload) => {
        if (!cancelled) {
          setMedications(payload.items)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMedicationError(error instanceof Error ? error.message : 'Failed to load medications')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMedicationLoading(false)
        }
      })

    void listLabResults(patientId)
      .then((payload) => {
        if (!cancelled) {
          setLabResults(payload.items)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMonitoringError(error instanceof Error ? error.message : 'Failed to load lab results')
        }
      })
      .finally(() => {
        if (!cancelled) setLabLoading(false)
      })

    void Promise.all([
      listMonitoringAlerts(patientId),
      getDiseaseProgression(patientId),
    ])
      .then(([alertsPayload, progressionPayload]) => {
        if (cancelled) return
        setAlerts(alertsPayload.items)
        setProgression(progressionPayload)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setMonitoringError(error instanceof Error ? error.message : 'Failed to load monitoring data')
      })
      .finally(() => {
        if (!cancelled) setMonitoringLoading(false)
      })

    setRiskStratLoading(true)
    setRiskStratError(null)
    void getRiskStratification(patientId)
      .then((payload) => {
        if (!cancelled) setRiskStrat(payload)
      })
      .catch((error: unknown) => {
        if (!cancelled) setRiskStratError(error instanceof Error ? error.message : 'Failed to load risk assessment')
      })
      .finally(() => {
        if (!cancelled) setRiskStratLoading(false)
      })

    setScreeningHistoryLoading(true)
    setScreeningHistoryError(null)
    void getScreeningHistory(patientId)
      .then((payload) => {
        if (!cancelled) setScreeningHistory(payload.modalities)
      })
      .catch((error: unknown) => {
        if (!cancelled) setScreeningHistoryError(error instanceof Error ? error.message : 'Failed to load screening history')
      })
      .finally(() => {
        if (!cancelled) setScreeningHistoryLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [patientId])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="border-b border-border/60 pb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Monitoring & Analytics</h1>
        <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-relaxed sm:text-base">{intro}</p>
      </div>

      {/* Patient context selector (doctor / caregiver only) — drives ALL fetches below. */}
      {user?.role !== 'patient' && (
        <Card className="border-primary/25 bg-primary/5 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Patient context</CardTitle>
            <CardDescription>
              {patientId
                ? `Viewing patient #${patientId}. All sections below load this patient's data.`
                : 'Enter a patient ID you have access to. All sections below will then load that patient’s data.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1 space-y-2 sm:max-w-xs">
                <Label htmlFor="monitoring-patient-id">Patient ID</Label>
                <Input
                  id="monitoring-patient-id"
                  type="number"
                  min={1}
                  placeholder="e.g. 14"
                  value={patientId}
                  onChange={(event) => setPatientId(event.target.value)}
                />
              </div>
              {patientId ? (
                <Button type="button" variant="outline" size="sm" onClick={() => setPatientId('')}>
                  Clear
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty-state hint when doctor/caregiver hasn't selected a patient yet. */}
      {user?.role !== 'patient' && !patientId ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-sm text-muted-foreground">
            <Info className="h-8 w-8 text-muted-foreground/60" aria-hidden />
            <p className="max-w-md leading-relaxed">
              Select a patient above to view their risk assessment, screening history, alerts, and
              disease progression.
            </p>
          </CardContent>
        </Card>
      ) : (
        <RiskStratificationCard
          data={riskStrat}
          loading={riskStratLoading}
          error={riskStratError}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>My Medications</CardTitle>
          <CardDescription>
            Verified prescription medications are persisted from uploaded documents. Always confirm treatment details with a clinician or pharmacist.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">

          {medicationError && <p className="text-sm text-destructive">{medicationError}</p>}
          {monitoringError && <p className="text-sm text-destructive">{monitoringError}</p>}

          {!patientId && (
            <p className="text-sm text-muted-foreground">
              Enter a patient ID to consult medications you have access to.
            </p>
          )}

          {patientId && medicationLoading && (
            <p className="text-sm text-muted-foreground">Loading medications...</p>
          )}

          {patientId && !medicationLoading && medications.length === 0 && !medicationError && (
            <p className="text-sm text-muted-foreground">No persisted medications available for this patient yet.</p>
          )}

          {medications.length > 0 && (
            <div className="monitoring-grid">
              {medications.map((medication) => (
                <div key={medication.id} className={`medication-card ${medication.verification_status}`}>
                  <div className="medication-header">
                    <div>
                      <div className="medication-name">{medication.name_display || medication.name_raw}</div>
                      {medication.name_display && medication.name_display !== medication.name_raw && (
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">OCR: {medication.name_raw}</div>
                      )}
                    </div>
                    <Badge variant="outline" className={getMedicationBadgeClass(medication.verification_status)}>
                      {medication.verification_status}
                    </Badge>
                  </div>

                  <div className="medication-details">
                    {medication.dosage && (
                      <div className="detail-item">
                        <Pill className="h-3 w-3 text-primary" />
                        <span>{medication.dosage}</span>
                      </div>
                    )}
                    {medication.frequency && (
                      <div className="detail-item">
                        <Clock className="h-3 w-3 text-primary" />
                        <span>{medication.frequency}</span>
                      </div>
                    )}
                    {medication.route && (
                      <div className="detail-item">
                        <ArrowUpRight className="h-3 w-3 text-primary" />
                        <span>{medication.route}</span>
                      </div>
                    )}
                    {medication.instructions && (
                      <div className="detail-item col-span-2 mt-1 italic text-[11px] text-muted-foreground border-t border-border/50 pt-1">
                        <span>Note: {medication.instructions}</span>
                      </div>
                    )}
                  </div>

                  <div
                    className="medication-source group hover:bg-muted/50 transition-colors rounded-md p-1 -m-1 cursor-pointer"
                    title="View Source Document"
                    onClick={() => {
                      if (isImage(medication.source_document_mime_type)) {
                        medication.source_document_preview_url &&
                          setSelectedDoc({
                            url: medication.source_document_preview_url,
                            filename: medication.source_document_filename,
                          })
                      } else if (medication.source_document_url) {
                        window.open(medication.source_document_url, '_blank')
                      }
                    }}
                  >
                    {medication.source_document_preview_url &&
                    isImage(medication.source_document_mime_type) ? (
                      <img
                        src={medication.source_document_preview_url}
                        alt="Source"
                        className="source-thumb"
                      />
                    ) : (
                      <div className="source-thumb flex items-center justify-center bg-muted">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium truncate">{medication.source_document_filename}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {new Date(medication.source_document_created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <ArrowUpRight className="h-3 w-3 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lab Results</CardTitle>
          <CardDescription>
            Detailed findings grouped by document. Click a report to expand its extracted metrics.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {patientId && labLoading && labResults.length === 0 && (
            <p className="text-sm text-muted-foreground">Loading lab results...</p>
          )}

          {patientId && !labLoading && labResults.length === 0 && !monitoringError && (
            <p className="text-sm text-muted-foreground">No persisted lab results available for this patient yet.</p>
          )}

          {labDocuments.length > 0 && (
            <Accordion type="single" collapsible className="w-full space-y-2 lab-results-accordion">
              {labDocuments.map((doc) => (
                <AccordionItem key={doc.id} value={doc.id} className="border rounded-lg px-4 bg-muted/30 lab-document-item">
                  <AccordionTrigger className="hover:no-underline py-4">
                    <div className="flex items-center gap-3 text-left w-full">
                      <div className="h-9 w-9 rounded-md bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden border">
                        {doc.preview_url && isImage(doc.mime_type) ? (
                          <img
                            src={doc.preview_url}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <FileText className="h-5 w-5 text-primary" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{doc.filename}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(doc.date).toLocaleDateString()} • {doc.results.length} findings
                        </div>
                      </div>
                      {doc.preview_url && (
                        <span
                          role="button"
                          tabIndex={0}
                          className="flex items-center gap-1 text-xs text-primary hover:underline px-2 py-1 rounded bg-primary/5 mr-2 cursor-pointer whitespace-nowrap"
                          onClick={(e) => {
                            e.stopPropagation()
                            if (isImage(doc.mime_type)) {
                              setSelectedDoc({ url: doc.preview_url!, filename: doc.filename })
                            } else if (doc.url) {
                              window.open(doc.url, '_blank')
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              e.stopPropagation()
                              setSelectedDoc({ url: doc.preview_url!, filename: doc.filename })
                            }
                          }}
                        >
                          <ArrowUpRight className="h-3 w-3" />
                          <span>View</span>
                        </span>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pt-2 pb-6">
                    <div className="grid gap-3">
                      {doc.results.map((result) => {
                        const rangeMatch = result.reference_range ? result.reference_range.match(/(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)/) : null;
                        const min = rangeMatch ? parseFloat(rangeMatch[1]) : null;
                        const max = rangeMatch ? parseFloat(rangeMatch[2]) : null;
                        const val = result.numeric_value;
                        
                        let position = 50;
                        if (min !== null && max !== null && val !== null) {
                          const padding = (max - min) * 0.2 || 1;
                          const displayMin = min - padding;
                          const displayMax = max + padding;
                          position = ((val - displayMin) / (displayMax - displayMin)) * 100;
                          position = Math.max(5, Math.min(95, position));
                        }

                        const isOutOfRange = result.is_out_of_range ?? (val !== null && min !== null && max !== null && (val < min || val > max));

                        return (
                          <div key={result.id} className={`lab-metric-card nested-lab-metric !bg-background border ${isOutOfRange ? 'out-of-range' : ''}`}>
                            <div className="lab-info !flex-row !items-center !justify-between !mb-0">
                              <span className="test-name">{result.test_name}</span>
                              <div className="flex items-baseline gap-2">
                                <span className={`lab-value-text ${isOutOfRange ? 'text-health-danger' : 'text-primary'}`}>
                                  {result.value}
                                </span>
                                <span className="lab-value-unit uppercase">{result.unit}</span>
                                {isOutOfRange && (
                                  <Badge variant="outline" className="bg-health-danger/10 text-health-danger border-health-danger/20 h-4 px-1 text-[9px]">
                                    HIGH/LOW
                                  </Badge>
                                )}
                              </div>
                            </div>
                            
                            {min !== null && max !== null && (
                              <div className="mt-2">
                                <div className="range-viz !h-1 !max-w-none">
                                  <div className="range-normal" style={{ left: '20%', width: '60%' }} />
                                  <div 
                                    className="range-marker !w-1.5 !h-1.5" 
                                    style={{ 
                                      left: `${position}%`,
                                      backgroundColor: isOutOfRange ? 'var(--health-danger)' : 'var(--primary)'
                                    }} 
                                  />
                                </div>
                                <div className="flex justify-between text-[9px] text-muted-foreground mt-1">
                                  <span>Ref: {min} - {max}</span>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="alerts" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-1.5 rounded-lg p-1 sm:h-11 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="alerts" className="gap-2 data-[state=active]:shadow-sm">
            <Bell className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
            Alerts
          </TabsTrigger>
          <TabsTrigger value="screening" className="gap-2 data-[state=active]:shadow-sm">
            <ScanSearch className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
            Screening history
          </TabsTrigger>
          <TabsTrigger value="progression" className="gap-2 data-[state=active]:shadow-sm">
            <TrendingUp className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
            Progression
          </TabsTrigger>
        </TabsList>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active Alerts</CardTitle>
              <CardDescription>
                {isDoctor
                  ? 'Assigned patients requiring immediate attention'
                  : isCaregiver
                    ? 'Important updates you may need to help with'
                    : 'Your latest health alerts and reminders'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {monitoringLoading && <p className="text-sm text-muted-foreground">Loading alerts...</p>}
              {!monitoringLoading && alerts.length === 0 && (
                <p className="text-sm text-muted-foreground">No alerts for this patient scope.</p>
              )}
              {alerts.map((alert) => {
                const titleLower = alert.title.toLowerCase()
                const isImprovement = titleLower.includes('improved')
                const AlertStatusIcon = isImprovement
                  ? CheckCircle2
                  : alert.severity === 'critical'
                    ? AlertCircle
                    : alert.severity === 'warning'
                      ? AlertTriangle
                      : Bell
                const iconWrapClass = isImprovement
                  ? 'bg-health-success/15 text-health-success ring-1 ring-health-success/25'
                  : alert.severity === 'critical'
                    ? 'bg-destructive/15 text-destructive ring-1 ring-destructive/25'
                    : alert.severity === 'warning'
                      ? 'bg-health-danger/10 text-health-danger ring-1 ring-health-danger/20'
                      : 'bg-muted text-muted-foreground ring-1 ring-border'
                return (
                  <div
                    key={alert.id}
                    className={`rounded-xl border p-4 shadow-sm transition-colors hover:bg-muted/40 ${
                      alert.severity === 'critical'
                        ? 'border-destructive/35 bg-destructive/5'
                        : alert.severity === 'warning'
                          ? 'border-health-danger/30 bg-health-danger/5'
                          : 'border-border bg-card'
                    }`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                      <div className="flex gap-3 flex-1 min-w-0">
                        <div
                          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${iconWrapClass}`}
                          aria-hidden
                        >
                          <AlertStatusIcon className="h-5 w-5" strokeWidth={2} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold">{alert.title}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {alert.patient_username}
                          </p>
                          <p className="text-sm text-muted-foreground mt-2 whitespace-pre-wrap leading-relaxed">
                            {alert.message}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end shrink-0">
                        <Badge className={getSeverityColor(alert.severity)}>{alert.severity}</Badge>
                        <span className="text-xs text-muted-foreground">{alert.relative_time}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="screening" className="space-y-4">
          <ScreeningHistoryTab
            modalities={screeningHistory}
            loading={screeningHistoryLoading}
            error={screeningHistoryError}
          />
        </TabsContent>

        <TabsContent value="progression" className="space-y-4">
          {isCaregiver ? (
            <Card>
              <CardHeader>
                <CardTitle>Progression Summary</CardTitle>
                <CardDescription>Caregiver access is limited to high-level trend visibility.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="font-medium">Clinician-level trends are hidden</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    You can continue following alerts, reminders, and care-plan updates here without seeing the full clinical progression view.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <DiseaseProgressionTracker
              data={progression}
              loading={monitoringLoading}
              error={monitoringError}
            />
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={!!selectedDoc} onOpenChange={(open) => !open && setSelectedDoc(null)}>
        <DialogContent className="max-w-4xl w-[95vw] h-[90vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="p-4 border-b">
            <DialogTitle className="truncate pr-8">{selectedDoc?.filename}</DialogTitle>
            <DialogDescription className="sr-only">
              Document preview for {selectedDoc?.filename}
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 bg-muted/10 relative overflow-auto p-4 flex items-center justify-center">
            {selectedDoc?.url && (
              previewError ? (
                <div className="flex h-full w-full flex-col items-center justify-center gap-3 rounded-sm border border-border bg-background p-6 text-center text-sm text-muted-foreground">
                  <Info className="h-6 w-6 text-muted-foreground" />
                  <p>Unable to preview this image directly. You can open it in a new tab to view the file.</p>
                  <a
                    href={selectedDoc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline"
                  >
                    Open in new tab
                  </a>
                </div>
              ) : (
                <img
                  src={selectedDoc.url}
                  alt={selectedDoc.filename}
                  className="max-w-full max-h-full object-contain shadow-lg rounded-sm"
                  onError={() => setPreviewError(true)}
                />
              )
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
