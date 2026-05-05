'use client'

import { useEffect, useState } from 'react'
import { Bell, FileText, MessageSquare, Plus, Stethoscope, Trash2, UserCheck, Users } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MedicalDocumentsSection } from '@/components/care-circle/medical-documents-section'
import { useAuth } from '@/components/auth-context'
import {
  getCareCirclePlan,
  inviteCaregiver,
  linkDoctor,
  listAvailableCaregivers,
  listAvailableDoctors,
  listCareCircleAppointments,
  listCareCircleTeam,
  listCareCircleUpdates,
  listMyCaregivers,
  listMyDoctors,
  listPendingInvitations,
  removeCaregiver,
  respondInvitation,
  unlinkDoctor,
  type AvailableCaregiver,
  type AvailableDoctor,
  type CareCircleAppointment,
  type CareCircleMember,
  type CareCircleMedicationGuidance,
  type CareCirclePlan,
  type CareCircleTask,
  type CareCircleUpdate,
  type CaregiverLink,
  type DoctorLink,
  type PendingInvitation,
} from '@/lib/carecircle-api'

// ── Status badge ──────────────────────────────────────────────────────────────

function LinkStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    accepted: 'bg-green-500/10 text-green-600 border-green-500/20',
    pending:  'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    rejected: 'bg-red-500/10 text-red-600 border-red-500/20',
  }
  return (
    <Badge variant="outline" className={variants[status] ?? 'bg-muted text-muted-foreground'}>
      {status}
    </Badge>
  )
}

// ── Manage care team (patient only) ──────────────────────────────────────────

function ManageCareTeam() {
  const [tab, setTab] = useState<'doctors' | 'caregivers'>('doctors')

  const [myDoctors, setMyDoctors] = useState<DoctorLink[]>([])
  const [availDoctors, setAvailDoctors] = useState<AvailableDoctor[]>([])
  const [myCaregivers, setMyCaregivers] = useState<CaregiverLink[]>([])
  const [availCaregivers, setAvailCaregivers] = useState<AvailableCaregiver[]>([])
  const [loading, setLoading] = useState(true)
  const [actionErr, setActionErr] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    void Promise.all([
      listMyDoctors(),
      listAvailableDoctors(),
      listMyCaregivers(),
      listAvailableCaregivers(),
    ])
      .then(([d, ad, c, ac]) => {
        setMyDoctors(d.items)
        setAvailDoctors(ad.items)
        setMyCaregivers(c.items)
        setAvailCaregivers(ac.items)
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleLinkDoctor(doctorId: number) {
    setActionErr(null)
    try {
      const link = await linkDoctor(doctorId)
      setMyDoctors(prev => [...prev, link])
      setAvailDoctors(prev => prev.filter(d => d.id !== doctorId))
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : 'Failed to link doctor')
    }
  }

  async function handleUnlinkDoctor(linkId: number, doctorId: number) {
    setActionErr(null)
    try {
      await unlinkDoctor(linkId)
      const removed = myDoctors.find(d => d.id === linkId)
      setMyDoctors(prev => prev.filter(d => d.id !== linkId))
      if (removed) {
        setAvailDoctors(prev => [...prev, {
          id: doctorId,
          name: removed.name,
          username: removed.username,
          specialization: removed.specialization,
          license_number: '',
          hospital_affiliation: removed.hospital_affiliation,
        }])
      }
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : 'Failed to remove doctor')
    }
  }

  async function handleInviteCaregiver(caregiverId: number) {
    setActionErr(null)
    try {
      const link = await inviteCaregiver(caregiverId)
      setMyCaregivers(prev => [...prev, link])
      setAvailCaregivers(prev => prev.filter(c => c.id !== caregiverId))
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : 'Failed to send invitation')
    }
  }

  async function handleRemoveCaregiver(linkId: number, caregiverId: number) {
    setActionErr(null)
    try {
      await removeCaregiver(linkId)
      const removed = myCaregivers.find(c => c.id === linkId)
      setMyCaregivers(prev => prev.filter(c => c.id !== linkId))
      if (removed) {
        setAvailCaregivers(prev => [...prev, {
          id: caregiverId,
          name: removed.name,
          username: removed.username,
          relationship: removed.relationship,
          is_professional: removed.is_professional,
        }])
      }
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : 'Failed to remove caregiver')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserCheck className="h-5 w-5" />
          Manage My Care Team
        </CardTitle>
        <CardDescription>Link a doctor for direct care, or invite a caregiver to support you.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Tabs */}
        <div className="flex gap-2 border-b border-border pb-2">
          {(['doctors', 'caregivers'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 text-sm font-medium rounded-t transition-colors capitalize ${
                tab === t
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {actionErr && <p className="text-sm text-destructive">{actionErr}</p>}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : tab === 'doctors' ? (
          <DoctorTab
            myDoctors={myDoctors}
            availDoctors={availDoctors}
            onLink={handleLinkDoctor}
            onUnlink={handleUnlinkDoctor}
          />
        ) : (
          <CaregiverTab
            myCaregivers={myCaregivers}
            availCaregivers={availCaregivers}
            onInvite={handleInviteCaregiver}
            onRemove={handleRemoveCaregiver}
          />
        )}
      </CardContent>
    </Card>
  )
}

function DoctorTab({
  myDoctors,
  availDoctors,
  onLink,
  onUnlink,
}: {
  myDoctors: DoctorLink[]
  availDoctors: AvailableDoctor[]
  onLink: (id: number) => void
  onUnlink: (linkId: number, doctorId: number) => void
}) {
  return (
    <div className="space-y-5">
      <section>
        <h4 className="text-sm font-semibold mb-2">Linked doctors ({myDoctors.length})</h4>
        {myDoctors.length === 0 ? (
          <p className="text-sm text-muted-foreground">No doctors linked yet.</p>
        ) : (
          <ul className="space-y-2">
            {myDoctors.map(link => (
              <li key={link.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-3">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(link.name)}`} />
                    <AvatarFallback><Stethoscope className="h-4 w-4" /></AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-medium">{link.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {link.specialization || 'General'}{link.hospital_affiliation ? ` · ${link.hospital_affiliation}` : ''}
                    </p>
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => onUnlink(link.id, link.doctor_id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-sm font-semibold mb-2">Available doctors ({availDoctors.length})</h4>
        {availDoctors.length === 0 ? (
          <p className="text-sm text-muted-foreground">All available doctors are already linked.</p>
        ) : (
          <ul className="space-y-2">
            {availDoctors.map(doc => (
              <li key={doc.id} className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/40 transition-colors">
                <div>
                  <p className="text-sm font-medium">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.specialization || 'General'}{doc.hospital_affiliation ? ` · ${doc.hospital_affiliation}` : ''}
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => onLink(doc.id)}>
                  <Plus className="h-3 w-3 mr-1" />
                  Link
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function CaregiverTab({
  myCaregivers,
  availCaregivers,
  onInvite,
  onRemove,
}: {
  myCaregivers: CaregiverLink[]
  availCaregivers: AvailableCaregiver[]
  onInvite: (id: number) => void
  onRemove: (linkId: number, caregiverId: number) => void
}) {
  return (
    <div className="space-y-5">
      <section>
        <h4 className="text-sm font-semibold mb-2">My caregivers ({myCaregivers.length})</h4>
        {myCaregivers.length === 0 ? (
          <p className="text-sm text-muted-foreground">No caregivers linked yet.</p>
        ) : (
          <ul className="space-y-2">
            {myCaregivers.map(link => (
              <li key={link.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-3">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(link.name)}`} />
                    <AvatarFallback>{link.name[0]}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-medium">{link.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {link.relationship || 'Caregiver'}{link.is_professional ? ' · Professional' : ''}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <LinkStatusBadge status={link.status} />
                  <Button
                    size="icon"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => onRemove(link.id, link.caregiver_id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-sm font-semibold mb-2">Available caregivers ({availCaregivers.length})</h4>
        {availCaregivers.length === 0 ? (
          <p className="text-sm text-muted-foreground">All available caregivers already invited.</p>
        ) : (
          <ul className="space-y-2">
            {availCaregivers.map(c => (
              <li key={c.id} className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/40 transition-colors">
                <div>
                  <p className="text-sm font-medium">{c.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.relationship || 'Caregiver'}{c.is_professional ? ' · Professional' : ''}
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => onInvite(c.id)}>
                  <Plus className="h-3 w-3 mr-1" />
                  Invite
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

// ── Pending invitations (caregiver only) ──────────────────────────────────────

function PendingInvitationsCard() {
  const [invitations, setInvitations] = useState<PendingInvitation[]>([])
  const [loading, setLoading] = useState(true)
  const [actionErr, setActionErr] = useState<string | null>(null)

  useEffect(() => {
    void listPendingInvitations()
      .then(r => setInvitations(r.items))
      .finally(() => setLoading(false))
  }, [])

  async function handleRespond(linkId: number, action: 'accept' | 'reject') {
    setActionErr(null)
    try {
      await respondInvitation(linkId, action)
      setInvitations(prev => prev.filter(i => i.id !== linkId))
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : 'Failed to respond')
    }
  }

  if (!loading && invitations.length === 0 && !actionErr) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Pending Invitations
        </CardTitle>
        <CardDescription>Patients who want to add you to their care team.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {actionErr && <p className="text-sm text-destructive">{actionErr}</p>}
        {loading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {!loading && invitations.length === 0 && (
          <p className="text-sm text-muted-foreground">No pending invitations.</p>
        )}
        {invitations.map(inv => (
          <div key={inv.id} className="flex items-center justify-between rounded-lg border border-border p-3">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(inv.name)}`} />
                <AvatarFallback>{inv.name[0]}</AvatarFallback>
              </Avatar>
              <div>
                <p className="text-sm font-medium">{inv.name}</p>
                <p className="text-xs text-muted-foreground">{new Date(inv.created_at).toLocaleDateString()}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handleRespond(inv.id, 'accept')}>Accept</Button>
              <Button size="sm" variant="outline" onClick={() => handleRespond(inv.id, 'reject')}>Reject</Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

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
    return () => { cancelled = true }
  }, [patientId])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Care Circle</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>

      {role !== 'patient' && (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="carecircle-patient-id">Patient ID</Label>
          <Input
            id="carecircle-patient-id"
            placeholder="Enter accessible patient ID"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
          />
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Patient: manage their care team */}
      {role === 'patient' && <ManageCareTeam />}

      {/* Caregiver: pending invitations inbox */}
      {role === 'caregiver' && <PendingInvitationsCard />}

      {/* Care team display */}
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
                  <AvatarFallback>{member.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{member.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {member.role}
                    {member.specialization ? ` · ${member.specialization}` : ''}
                    {member.relationship ? ` · ${member.relationship}` : ''}
                  </p>
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
                  {carePlans.slice(0, 3).map(plan => (
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
                  {medGuidance.slice(0, 3).map(item => (
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
                  {tasks.slice(0, 3).map(task => (
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
            {updates.map(update => (
              <div key={update.id} className="p-3 border border-border rounded-lg hover:bg-muted/50 transition-colors">
                <p className="font-medium text-sm">{update.from_name}</p>
                <p className="text-sm text-muted-foreground mt-1">{update.summary}</p>
                <p className="text-xs text-muted-foreground mt-2">{new Date(update.created_at).toLocaleString()}</p>
              </div>
            ))}
            <Button variant="outline" className="w-full">View All</Button>
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
              {appointments.map(appointment => (
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
