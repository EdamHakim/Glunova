'use client'

import { useEffect, useState } from 'react'
import { Stethoscope, AlertTriangle, Image as ImageIcon, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import RoleGuard from '@/components/auth/role-guard'
import { DFUSegmentationPanel } from '@/components/clinical/dfu-segmentation-panel'
import { ThermalFootPanel } from '@/components/clinical/thermal-foot-panel'
import {
  getClinicalSummary,
  listClinicalPriorities,
  listImagingQueue,
  listPreconsultation,
  type ClinicalPriorityRow,
  type ImagingQueueRow,
  type PreconsultationRow,
} from '@/lib/clinical-api'

export default function ClinicalPage() {
  const [summary, setSummary] = useState({ critical_cases: 0, high_risk: 0, stable: 0, pending_review: 0 })
  const [priorities, setPriorities] = useState<ClinicalPriorityRow[]>([])
  const [imagingQueue, setImagingQueue] = useState<ImagingQueueRow[]>([])
  const [preconsultation, setPreconsultation] = useState<PreconsultationRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all([getClinicalSummary(), listClinicalPriorities(), listImagingQueue(), listPreconsultation()])
      .then(([summaryPayload, prioritiesPayload, imagingPayload, preconsultationPayload]) => {
        if (cancelled) return
        setSummary(summaryPayload)
        setPriorities(prioritiesPayload.items)
        setImagingQueue(imagingPayload.items)
        setPreconsultation(preconsultationPayload.items)
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
      title="Clinical support unavailable"
      description="Clinical decision support is reserved for doctor accounts."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Clinical Decision Support</h1>
          <p className="text-muted-foreground mt-2">AI-powered clinical insights and patient prioritization</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Critical Cases</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-destructive">{summary.critical_cases}</div>
              <p className="text-xs text-destructive flex items-center gap-1 mt-1">
                <AlertTriangle className="h-3 w-3" /> Require immediate attention
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">High Risk</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-health-danger">{summary.high_risk}</div>
              <p className="text-xs text-health-danger mt-1">Follow-up recommended</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Stable Patients</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-health-success">{summary.stable}</div>
              <p className="text-xs text-health-success mt-1">Routine monitoring</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Pending Review</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-primary">{summary.pending_review}</div>
              <p className="text-xs text-muted-foreground mt-1">Medical image analysis</p>
            </CardContent>
          </Card>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {loading && <p className="text-sm text-muted-foreground">Loading clinical insights...</p>}

        <ThermalFootPanel />
        <DFUSegmentationPanel />

      {/* Patient Prioritization List */}
        <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Patient Prioritization List
          </CardTitle>
          <CardDescription>AI-ranked by clinical urgency</CardDescription>
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
                    <Button variant="outline" size="sm">
                      Review
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
        </Card>

      {/* Medical Image Analysis */}
        <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Medical Image Analysis Queue
          </CardTitle>
          <CardDescription>Pending radiology & pathology reviews</CardDescription>
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
                    Pending
                  </Badge>
                  <Badge variant="outline">Severity {row.severity_grade}</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
        </Card>

      {/* Pre-Consultation Summary */}
        <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Stethoscope className="h-5 w-5" />
            Pre-Consultation Summary
          </CardTitle>
          <CardDescription>Quick reference for upcoming consultations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {preconsultation.map((item) => (
              <div key={item.id} className="p-4 border border-border rounded-lg">
                <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10">
                      <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(item.patient_name)}`} />
                      <AvatarFallback>{item.patient_name.slice(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium">{item.patient_name}</p>
                      <p className="text-xs text-muted-foreground">Assigned patient</p>
                    </div>
                  </div>
                  <Clock className="h-5 w-5 text-primary" />
                </div>
                <div className="space-y-2 text-sm">
                  <p><span className="font-medium">Chief Complaint:</span> {item.chief_complaint}</p>
                  <p><span className="font-medium">Priority:</span> {item.priority}</p>
                  <p><span className="font-medium">Recommendation:</span> {item.recommendation}</p>
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
