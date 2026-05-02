'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Monitoring & Analytics</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>

      {/* Patient context selector (doctor / caregiver only) — drives ALL fetches below. */}
      {user?.role !== 'patient' && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Patient context</CardTitle>
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
                <button
                  type="button"
                  className="rounded-md border px-3 py-2 text-sm hover:bg-muted transition-colors"
                  onClick={() => setPatientId('')}
                >
                  Clear
                </button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty-state hint when doctor/caregiver hasn't selected a patient yet. */}
      {user?.role !== 'patient' && !patientId ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Select a patient above to view their risk assessment, screening history, alerts, and
            disease progression.
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Medication</TableHead>
                  <TableHead>Dosage & Frequency</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {medications.map((medication) => (
                  <TableRow key={medication.id}>
                    <TableCell className="whitespace-normal">
                      <div className="font-medium">{medication.name_display || medication.name_raw}</div>
                      {medication.name_display && medication.name_display !== medication.name_raw && (
                        <div className="text-xs text-muted-foreground">OCR: {medication.name_raw}</div>
                      )}
                      {medication.rxcui && (
                        <div className="text-xs text-muted-foreground">RxCUI: {medication.rxcui}</div>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-normal text-sm text-muted-foreground">
                      {[medication.dosage, medication.frequency, medication.duration, medication.route]
                        .filter(Boolean)
                        .join(' · ') || 'Not available'}
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      <Badge variant="outline" className={getMedicationBadgeClass(medication.verification_status)}>
                        {medication.verification_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-normal text-sm">
                      {medication.source_document_preview_url ? (
                        <img
                          src={medication.source_document_preview_url}
                          alt={medication.source_document_filename}
                          className="mb-2 h-16 w-16 rounded-md border border-border object-cover"
                        />
                      ) : null}
                      <div>{medication.source_document_filename}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(medication.source_document_created_at).toLocaleDateString()}
                      </div>
                      {medication.source_document_count > 1 && (
                        <div className="text-xs text-muted-foreground">
                          Also seen in {medication.source_document_count - 1} other document{medication.source_document_count > 2 ? 's' : ''}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Latest Lab Results</CardTitle>
          <CardDescription>
            Structured values extracted from uploaded lab reports are available here for follow-up and monitoring.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {patientId && labLoading && labResults.length === 0 && (
            <p className="text-sm text-muted-foreground">Loading lab results...</p>
          )}

          {patientId && !labLoading && labResults.length === 0 && !monitoringError && (
            <p className="text-sm text-muted-foreground">No persisted lab results available for this patient yet.</p>
          )}

          {labResults.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Test</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Observed</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {labResults.map((result) => (
                  <TableRow key={result.id}>
                    <TableCell className="whitespace-normal font-medium">{result.test_name}</TableCell>
                    <TableCell className="whitespace-normal text-sm text-muted-foreground">
                      {result.value}
                      {result.unit ? ` ${result.unit}` : ''}
                    </TableCell>
                    <TableCell className="whitespace-normal text-sm text-muted-foreground">
                      {new Date(result.observed_at || result.source_document_created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="whitespace-normal text-sm">
                      <div>{result.source_document_filename}</div>
                      <div className="text-xs text-muted-foreground">
                        Uploaded {new Date(result.source_document_created_at).toLocaleDateString()}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="alerts" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-2 sm:h-10 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="screening">Screening History</TabsTrigger>
          <TabsTrigger value="progression">Progression</TabsTrigger>
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
                const tierEmoji = isImprovement
                  ? '✅'
                  : alert.severity === 'critical'
                    ? '🚨'
                    : alert.severity === 'warning'
                      ? '⚠️'
                      : '🔔'
                return (
                  <div
                    key={alert.id}
                    className={`p-4 border rounded-lg hover:bg-muted/50 transition-colors ${
                      alert.severity === 'critical'
                        ? 'border-destructive/30 bg-destructive/5'
                        : alert.severity === 'warning'
                          ? 'border-health-danger/30 bg-health-danger/5'
                          : 'border-border'
                    }`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                      <div className="flex gap-3 flex-1 min-w-0">
                        <span className="text-xl shrink-0 leading-tight" aria-hidden>{tierEmoji}</span>
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
    </div>
  )
}
