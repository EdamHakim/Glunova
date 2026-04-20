'use client'

import { useEffect, useState } from 'react'
import { MessageSquare, FileText, Bell, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { MedicalDocumentsSection } from '@/components/care-circle/medical-documents-section'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  getCareCirclePlan,
  listCareCircleAppointments,
  listCareCircleTeam,
  listCareCircleUpdates,
  type CareCircleAppointment,
  type CareCircleMember,
  type CareCircleMedicationGuidance,
  type CareCirclePlan,
  type CareCircleTask,
  type CareCircleUpdate,
} from '@/lib/carecircle-api'

export default function CareCirclePage() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [members, setMembers] = useState<CareCircleMember[]>([])
  const [updates, setUpdates] = useState<CareCircleUpdate[]>([])
  const [carePlans, setCarePlans] = useState<CareCirclePlan[]>([])
  const [tasks, setTasks] = useState<CareCircleTask[]>([])
  const [medGuidance, setMedGuidance] = useState<CareCircleMedicationGuidance[]>([])
  const [appointments, setAppointments] = useState<CareCircleAppointment[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const role = user?.role
  const canClinicallyEdit = role === 'doctor'
  const intro =
    role === 'doctor'
      ? 'Coordinate with caregivers and keep shared care plans aligned for assigned patients.'
      : role === 'caregiver'
        ? 'Stay informed, help with routines, and support the linked patient day to day.'
        : 'Connect with family, caregivers, and healthcare providers.'
  useEffect(() => {
    if (user?.role === 'patient') setPatientId(user.id)
  }, [user])

  useEffect(() => {
    if (!patientId) {
      setMembers([])
      setUpdates([])
      setCarePlans([])
      setTasks([])
      setMedGuidance([])
      setAppointments([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all([
      listCareCircleTeam(patientId),
      listCareCircleUpdates(patientId),
      getCareCirclePlan(patientId),
      listCareCircleAppointments(patientId),
    ])
      .then(([teamPayload, updatesPayload, planPayload, apptsPayload]) => {
        if (cancelled) return
        setMembers(teamPayload.items)
        setUpdates(updatesPayload.items)
        setCarePlans(planPayload.care_plans)
        setTasks(planPayload.tasks)
        setMedGuidance(planPayload.medication_guidance)
        setAppointments(apptsPayload.items)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load care circle data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [patientId])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Care Circle</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>
      {user?.role !== 'patient' && (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="carecircle-patient-id">Patient ID</Label>
          <Input
            id="carecircle-patient-id"
            placeholder="Enter accessible patient ID"
            value={patientId}
            onChange={(event) => setPatientId(event.target.value)}
          />
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Care Team
          </CardTitle>
          <CardDescription>Family members and healthcare providers</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading care team...</p>}
          {!loading && members.length === 0 && (
            <p className="text-sm text-muted-foreground">No linked team members for this patient scope.</p>
          )}
          {members.map((member, idx) => (
            <div
              key={`${member.id}-${idx}`}
              className="flex flex-col gap-3 border border-border p-4 rounded-lg transition-colors hover:bg-muted/50 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-center gap-4">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(member.name)}`} />
                  <AvatarFallback>{member.name.split(' ').map((n) => n[0]).join('')}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{member.name}</p>
                  <p className="text-xs text-muted-foreground">{member.role}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 self-end sm:self-auto">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  {member.status}
                </Badge>
                <Button size="icon" variant="ghost">
                  <MessageSquare className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <MedicalDocumentsSection />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Shared Care Plan
            </CardTitle>
            <CardDescription>
              {canClinicallyEdit
                ? 'Shared plan you can refine with medical guidance'
                : 'Current health plan shared with the care circle'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Daily Routine</h4>
              {carePlans.length === 0 ? (
                <p className="text-sm text-muted-foreground">No care plan notes yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {carePlans.slice(0, 3).map((plan) => (
                    <li key={plan.id}>
                      {plan.patient_name}: {plan.notes || 'No notes provided.'}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Medications</h4>
              {medGuidance.length === 0 ? (
                <p className="text-sm text-muted-foreground">No medication guidance available.</p>
              ) : (
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {medGuidance.slice(0, 3).map((item) => (
                    <li key={item.id}>
                      {item.medication_name} • {item.guidance}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Goals</h4>
              {tasks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No tasks defined yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {tasks.slice(0, 3).map((task) => (
                    <li key={task.id}>
                      {task.title} ({task.status})
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-lg border border-dashed border-border p-4">
              <p className="font-medium">{canClinicallyEdit ? 'Doctor note' : 'Participation note'}</p>
              <p className="text-sm text-muted-foreground mt-2">
                {canClinicallyEdit
                  ? 'You can update this plan clinically, but document and monitoring access remain relationship-scoped.'
                  : 'You can follow this plan and coordinate around it, but medically authoritative edits remain clinician-led.'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Updates & Messages
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && <p className="text-sm text-muted-foreground">Loading updates...</p>}
            {!loading && updates.length === 0 && (
              <p className="text-sm text-muted-foreground">No care circle updates for this patient scope.</p>
            )}
            {updates.map((update) => (
              <div key={update.id} className="p-3 border border-border rounded-lg hover:bg-muted/50 transition-colors">
                <p className="font-medium text-sm">{update.from_name}</p>
                <p className="text-sm text-muted-foreground mt-1">{update.summary}</p>
                <p className="text-xs text-muted-foreground mt-2">{new Date(update.created_at).toLocaleString()}</p>
              </div>
            ))}
            <Button variant="outline" className="w-full">
              View All
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Upcoming Appointments
          </CardTitle>
          <CardDescription>
            {role === 'doctor'
              ? 'Coordinate next steps with the support network'
              : 'Shared care timeline'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="h-48 border border-border rounded-lg bg-muted/30 p-4 overflow-y-auto space-y-3">
              {loading && <p className="text-sm text-muted-foreground">Loading appointments...</p>}
              {!loading && appointments.length === 0 && (
                <p className="text-sm text-muted-foreground">No appointments available for this patient scope.</p>
              )}
              {appointments.map((appointment) => (
                <div key={appointment.id} className="rounded-lg border border-border bg-background p-3">
                  <p className="text-sm font-medium">{appointment.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {appointment.patient_name} • {new Date(appointment.starts_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Doctor: {appointment.doctor_name} • Caregiver: {appointment.caregiver_name}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder={
                  role === 'doctor'
                    ? 'Appointment management stays read-only in this view'
                    : 'Scheduling actions stay read-only in this view'
                }
                disabled
                className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-sm"
              />
              <Button size="icon" disabled>
                <MessageSquare className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
