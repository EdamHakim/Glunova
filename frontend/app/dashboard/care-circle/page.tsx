'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, Bell, Bot, Calendar, Plus, Stethoscope, Trash2, UserCheck, UserRoundSearch } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import RoleGuard from '@/components/auth/role-guard'
import { MedicalDocumentsSection } from '@/components/care-circle/medical-documents-section'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { useAuth } from '@/components/auth-context'
import {
  inviteCaregiver,
  linkDoctor,
  listAvailableCaregivers,
  listAvailableDoctors,
  listCareCircleAppointments,
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
  type CareCircleUpdate,
  type CaregiverLink,
  type DoctorLink,
  type PendingInvitation,
} from '@/lib/carecircle-api'

// ── Status badge ──────────────────────────────────────────────────────────────

function LinkStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    accepted: 'bg-green-500/10 text-green-600 border-green-500/20',
    pending: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
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
              className={`px-4 py-1.5 text-sm font-medium rounded-t transition-colors capitalize ${tab === t
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

// ── Main page (patients & caregivers only) ───────────────────────────────────

function CareCircleContent() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [updates, setUpdates] = useState<CareCircleUpdate[]>([])
  const [appointments, setAppointments] = useState<CareCircleAppointment[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const role = user?.role
  const caregiverNeedsPatientId = role === 'caregiver'
  const intro =
    role === 'caregiver'
      ? 'Stay informed, help with routines, and support the linked patient day to day.'
      : 'Connect with family, caregivers, and healthcare providers.'

  useEffect(() => {
    if (user?.role === 'patient') setPatientId(user.id)
  }, [user])

  useEffect(() => {
    if (!patientId) {
      setUpdates([])
      setAppointments([])
      return
    }
    const showUpdates = role === 'caregiver'
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all([
      listCareCircleAppointments(patientId),
      showUpdates ? listCareCircleUpdates(patientId) : Promise.resolve({ items: [] as CareCircleUpdate[] }),
    ])
      .then(([apptsPayload, updatesPayload]) => {
        if (cancelled) return
        setAppointments(apptsPayload.items)
        setUpdates(showUpdates ? updatesPayload.items : [])
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load care circle data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [patientId, role])

  return (
    <div className="relative min-h-[calc(100dvh-6rem)]">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-linear-to-b from-primary/8 via-primary/2 to-transparent"
        aria-hidden
      />
      <div className="relative mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
        <header className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Care coordination</p>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Care Circle</h1>
            <p className="text-base leading-relaxed text-muted-foreground">{intro}</p>
          </div>

          {caregiverNeedsPatientId && (
            <Card className="w-full shrink-0 border-dashed bg-muted/25 shadow-sm lg:max-w-md">
              <CardHeader className="space-y-1 pb-2 pt-5">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <UserRoundSearch className="h-4 w-4" />
                  <span className="text-xs font-semibold uppercase tracking-wide">Patient context</span>
                </div>
                <CardTitle className="text-base">Whose care circle are you viewing?</CardTitle>
                <CardDescription>
                  Choose a linked patient. If you support only one, they are selected automatically.
                </CardDescription>
              </CardHeader>
              <CardContent className="pb-5">
                <DoctorPatientPicker
                  id="carecircle-patient-id"
                  label="Patient"
                  description="Search by name — patients you are linked to as a caregiver."
                  value={patientId}
                  onChange={setPatientId}
                  className="[&_button]:bg-background/80"
                />
              </CardContent>
            </Card>
          )}
        </header>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {role === 'patient' && <ManageCareTeam />}

        {role === 'caregiver' && <PendingInvitationsCard />}

        <section className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Health records</h2>
              <p className="text-sm text-muted-foreground">Uploads and extractions for the selected context.</p>
            </div>
          </div>
          <MedicalDocumentsSection linkedPatientId={role === 'caregiver' ? patientId : undefined} />
        </section>

        {caregiverNeedsPatientId && !patientId ? (
          <Card className="border-dashed border-muted-foreground/25 bg-muted/15">
            <CardContent className="flex flex-col items-center justify-center gap-2 py-16 text-center sm:py-20">
              <div className="rounded-full border border-border bg-background p-3 shadow-sm">
                <UserRoundSearch className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="max-w-sm text-sm font-medium text-foreground">Select a patient first</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Updates, appointments, and shared documents load after you choose a patient above.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div
            className={
              role === 'caregiver'
                ? 'grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-stretch'
                : 'grid grid-cols-1 gap-6'
            }
          >
            {role === 'caregiver' && (
              <Card className="flex flex-col border-border/80 shadow-sm lg:col-span-7">
                <CardHeader className="border-b border-border/60 bg-muted/20 pb-4">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Bell className="h-4 w-4" />
                    </span>
                    Updates &amp; messages
                  </CardTitle>
                  <CardDescription>Recent notes from the care team and care agent.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col p-0">
                  {loading && (
                    <p className="p-5 text-sm text-muted-foreground">Loading updates…</p>
                  )}
                  {!loading && updates.length === 0 && (
                    <p className="p-5 text-sm text-muted-foreground">No updates yet for this patient.</p>
                  )}
                  {!loading && updates.length > 0 && (
                    <ScrollArea className="h-[min(420px,50vh)] sm:h-[min(480px,55vh)]">
                      <ul className="divide-y divide-border/80 p-2">
                        {updates.map((update) => (
                          <li
                            key={update.id}
                            className="px-3 py-3 transition-colors hover:bg-muted/40 sm:px-4 sm:py-4"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <p className="font-medium leading-snug">{update.from_name}</p>
                              {update.source === 'agent' && (
                                <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold text-violet-700 dark:text-violet-300">
                                  <Bot className="h-3 w-3" />
                                  AI
                                </span>
                              )}
                            </div>
                            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{update.summary}</p>
                            <p className="mt-2 text-xs text-muted-foreground tabular-nums">
                              {new Date(update.created_at).toLocaleString()}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>
            )}

            <Card
              className={
                role === 'caregiver'
                  ? 'flex flex-col border-border/80 shadow-sm lg:col-span-5'
                  : 'flex flex-col border-border/80 shadow-sm'
              }
            >
              <CardHeader className="border-b border-border/60 bg-muted/20 pb-4">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Calendar className="h-4 w-4" />
                  </span>
                  Appointments
                </CardTitle>
                <CardDescription>
                  {role === 'patient'
                    ? 'Your shared schedule with the care team.'
                    : 'Scheduled touchpoints for the patient you support.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col p-0">
                {loading && (
                  <p className="p-5 text-sm text-muted-foreground">Loading appointments…</p>
                )}
                {!loading && appointments.length === 0 && (
                  <p className="p-5 text-sm text-muted-foreground">No appointments on file for this patient.</p>
                )}
                {!loading && appointments.length > 0 && (
                  <ScrollArea className="h-[min(420px,50vh)] sm:h-[min(480px,55vh)]">
                    <ul className="space-y-3 p-4">
                      {appointments.map((appointment) => (
                        <li
                          key={appointment.id}
                          className="rounded-xl border border-border/80 bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
                        >
                          <p className="font-medium leading-snug">{appointment.title}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {appointment.patient_name}
                            <span className="text-border"> · </span>
                            {new Date(appointment.starts_at).toLocaleString()}
                          </p>
                          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                            <span className="font-medium text-foreground/80">Doctor:</span> {appointment.doctor_name}
                            <br />
                            <span className="font-medium text-foreground/80">Caregiver:</span>{' '}
                            {appointment.caregiver_name}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </ScrollArea>
                )}
                <p className="border-t border-border/60 px-4 py-3 text-xs text-muted-foreground">
                  Scheduling changes are managed outside this view.
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}

export default function CareCirclePage() {
  return (
    <RoleGuard
      allowedRoles={['patient', 'caregiver']}
      title="Care Circle is not available for clinicians"
      description="Care Circle is for patients and caregivers. Use Monitoring for assigned patients and Clinical Support where applicable."
    >
      <CareCircleContent />
    </RoleGuard>
  )
}
