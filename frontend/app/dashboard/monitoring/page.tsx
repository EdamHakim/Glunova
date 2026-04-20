'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { listMedications, type PatientMedicationRow } from '@/lib/medications-api'
import {
  getMonitoringProgression,
  listMonitoringAlerts,
  listMonitoringTimeline,
  type MonitoringAlert,
  type MonitoringTierSummary,
  type MonitoringTimelineItem,
} from '@/lib/monitoring-api'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

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
  const [timelineEvents, setTimelineEvents] = useState<MonitoringTimelineItem[]>([])
  const [progression, setProgression] = useState<MonitoringTierSummary[]>([])
  const [medicationError, setMedicationError] = useState<string | null>(null)
  const [monitoringError, setMonitoringError] = useState<string | null>(null)
  const [medicationLoading, setMedicationLoading] = useState(false)
  const [monitoringLoading, setMonitoringLoading] = useState(false)
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
      setTimelineEvents([])
      setProgression([])
      return
    }

    let cancelled = false
    setMedicationLoading(true)
    setMedicationError(null)
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

    void Promise.all([
      listMonitoringAlerts(patientId),
      listMonitoringTimeline(patientId),
      getMonitoringProgression(patientId),
    ])
      .then(([alertsPayload, timelinePayload, progressionPayload]) => {
        if (cancelled) return
        setAlerts(alertsPayload.items)
        setTimelineEvents(timelinePayload.items)
        setProgression(progressionPayload.tiers)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setMonitoringError(error instanceof Error ? error.message : 'Failed to load monitoring data')
      })
      .finally(() => {
        if (!cancelled) setMonitoringLoading(false)
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

      <Card>
        <CardHeader>
          <CardTitle>My Medications</CardTitle>
          <CardDescription>
            Verified prescription medications are persisted from uploaded documents. Always confirm treatment details with a clinician or pharmacist.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {user?.role !== 'patient' && (
            <div className="max-w-sm space-y-2">
              <Label htmlFor="monitoring-patient-id">Patient ID</Label>
              <Input
                id="monitoring-patient-id"
                placeholder="Enter accessible patient ID"
                value={patientId}
                onChange={(event) => setPatientId(event.target.value)}
              />
            </div>
          )}

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

      <Tabs defaultValue="alerts" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-2 sm:h-10 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
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
              {alerts.map((alert) => (
                <div key={alert.id} className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div className="flex gap-4 flex-1">
                      <AlertCircle
                        className={`h-5 w-5 mt-0.5 shrink-0 ${
                          alert.severity === 'critical'
                            ? 'text-destructive'
                            : alert.severity === 'warning'
                              ? 'text-health-danger'
                              : 'text-health-warning'
                        }`}
                      />
                      <div>
                        <p className="font-medium">{alert.title}</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {alert.patient_username} - {alert.message}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                      <Badge className={getSeverityColor(alert.severity)}>{alert.severity}</Badge>
                      <span className="text-xs text-muted-foreground">{alert.relative_time}</span>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Patient Event Timeline</CardTitle>
              <CardDescription>
                {isCaregiver ? 'Recent shareable events and care activities' : 'Recent health events and assessments'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {monitoringLoading && <p className="text-sm text-muted-foreground">Loading timeline...</p>}
                {!monitoringLoading && timelineEvents.length === 0 && (
                  <p className="text-sm text-muted-foreground">No timeline events available.</p>
                )}
                {timelineEvents.map((event, idx) => (
                  <div key={idx} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                        <Clock className="h-5 w-5 text-primary" />
                      </div>
                      {idx < timelineEvents.length - 1 && <div className="w-0.5 h-12 bg-border mt-2" />}
                    </div>
                    <div className="pb-4">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{event.title}</p>
                        <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">{event.value}</span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">{event.patient_username}</p>
                      <p className="text-xs text-muted-foreground mt-1">{event.relative_time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
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
            <Card>
              <CardHeader>
                <CardTitle>Disease Progression Charts</CardTitle>
                <CardDescription>
                  {isDoctor ? 'Long-term trends across assigned patient risk categories' : 'Long-term health trends by patient risk category'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {monitoringLoading && <p className="text-sm text-muted-foreground">Loading progression data...</p>}
                {!monitoringLoading &&
                  progression.map((tier) => (
                    <div key={tier.tier}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-medium capitalize">{tier.tier} Risk Patients</span>
                        <Badge
                          variant="outline"
                          className={
                            tier.tier === 'low'
                              ? 'bg-health-success/10 text-health-success border-health-success/20'
                              : tier.tier === 'moderate'
                                ? 'bg-health-warning/10 text-health-warning border-health-warning/20'
                                : tier.tier === 'high'
                                  ? 'bg-health-danger/10 text-health-danger border-health-danger/20'
                                  : 'bg-destructive/10 text-destructive border-destructive/20'
                          }
                        >
                          {tier.count} patients
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">Avg Risk Score</span>
                          <span className="font-medium">{Math.round(tier.avg_score * 100)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className={
                              tier.tier === 'low'
                                ? 'bg-health-success h-2 rounded-full'
                                : tier.tier === 'moderate'
                                  ? 'bg-health-warning h-2 rounded-full'
                                  : tier.tier === 'high'
                                    ? 'bg-health-danger h-2 rounded-full'
                                    : 'bg-destructive h-2 rounded-full'
                            }
                            style={{ width: `${Math.min(100, Math.round(tier.avg_score * 100))}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
