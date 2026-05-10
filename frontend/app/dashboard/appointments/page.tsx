'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { differenceInCalendarDays, format, startOfToday } from 'date-fns'
import { CalendarDays, CalendarPlus, Clock, Loader2, Stethoscope, X } from 'lucide-react'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { AssignedPatientRow } from '@/lib/dashboard-api'
import {
  cancelAppointment,
  directBookAppointment,
  getAvailableTimes,
  getDoctorAvailability,
  listBookingDoctorsForPatient,
  listCareCircleAppointments,
  listMyDoctors,
  type AvailableTimeSlot,
  type CareCircleAppointment,
  type DoctorAvailability,
  type DoctorLink,
} from '@/lib/carecircle-api'

function jsToBackendDay(jsDay: number): number {
  return (jsDay + 6) % 7
}

function relativeDay(dateStr: string): string {
  const diff = differenceInCalendarDays(new Date(dateStr), startOfToday())
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff > 0 && diff < 7) return `In ${diff} days`
  return format(new Date(dateStr), 'EEE d MMM')
}

function StepBadge({ n }: { n: number }) {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground shrink-0 select-none">
      {n}
    </span>
  )
}

export default function AppointmentsPage() {
  const { user } = useAuth()
  const isCaregiver = user?.role === 'caregiver'
  const isPatient = user?.role === 'patient'

  const [caregiverPatientId, setCaregiverPatientId] = useState('')
  const [selectedPatientLabel, setSelectedPatientLabel] = useState<string | null>(null)

  const [doctors, setDoctors] = useState<DoctorLink[]>([])
  const [doctorId, setDoctorId] = useState('')
  const [doctorAvailability, setDoctorAvailability] = useState<DoctorAvailability[]>([])
  const [selectedDate, setSelectedDate] = useState<Date | undefined>()
  const [availableSlots, setAvailableSlots] = useState<AvailableTimeSlot[]>([])
  const [appointments, setAppointments] = useState<CareCircleAppointment[]>([])
  const [title, setTitle] = useState('')

  const [loadingDoctors, setLoadingDoctors] = useState(true)
  const [loadingAvailability, setLoadingAvailability] = useState(false)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [loadingAppts, setLoadingAppts] = useState(true)
  const [bookingSlot, setBookingSlot] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const bookingContextReady = isPatient || (isCaregiver && caregiverPatientId !== '')
  const activeDays = new Set(doctorAvailability.map((a) => a.day_of_week))
  const selectedDoctor = doctors.find((d) => String(d.doctor_id) === doctorId)

  function isDateDisabled(date: Date): boolean {
    if (date < startOfToday()) return true
    if (doctorAvailability.length === 0) return false
    return !activeDays.has(jsToBackendDay(date.getDay()))
  }

  const morningSlots = availableSlots.filter((s) => new Date(s.starts_at).getHours() < 12)
  const afternoonSlots = availableSlots.filter((s) => new Date(s.starts_at).getHours() >= 12)

  const loadUpcoming = useCallback(() => {
    if (!user) return
    if (isCaregiver && !caregiverPatientId) {
      setAppointments([])
      setLoadingAppts(false)
      return
    }
    setLoadingAppts(true)
    listCareCircleAppointments(isCaregiver ? caregiverPatientId : undefined)
      .then((r) => setAppointments(r.items.filter((a) => a.status === 'scheduled')))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load appointments'))
      .finally(() => setLoadingAppts(false))
  }, [user, isCaregiver, caregiverPatientId])

  useEffect(() => {
    if (!isPatient) return
    setLoadingDoctors(true)
    listMyDoctors()
      .then((r) => { setDoctors(r.items); setDoctorId(r.items[0] ? String(r.items[0].doctor_id) : '') })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load doctors'))
      .finally(() => setLoadingDoctors(false))
  }, [isPatient])

  useEffect(() => {
    if (!isCaregiver) return
    if (!caregiverPatientId) { setDoctors([]); setDoctorId(''); setLoadingDoctors(false); return }
    setLoadingDoctors(true)
    listBookingDoctorsForPatient(caregiverPatientId)
      .then((r) => { setDoctors(r.items); setDoctorId(r.items[0] ? String(r.items[0].doctor_id) : '') })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load doctors'))
      .finally(() => setLoadingDoctors(false))
  }, [isCaregiver, caregiverPatientId])

  useEffect(() => { loadUpcoming() }, [loadUpcoming])

  useEffect(() => {
    const id = parseInt(doctorId, 10)
    if (!Number.isFinite(id) || !bookingContextReady) {
      setDoctorAvailability([]); setSelectedDate(undefined); setAvailableSlots([]); return
    }
    setLoadingAvailability(true)
    setSelectedDate(undefined)
    setAvailableSlots([])
    getDoctorAvailability(id, isCaregiver ? { patientId: caregiverPatientId } : undefined)
      .then((r) => setDoctorAvailability(r.items))
      .catch(() => setDoctorAvailability([]))
      .finally(() => setLoadingAvailability(false))
  }, [doctorId, bookingContextReady, isCaregiver, caregiverPatientId])

  useEffect(() => {
    const id = parseInt(doctorId, 10)
    if (!selectedDate || !Number.isFinite(id)) { setAvailableSlots([]); return }
    setLoadingSlots(true)
    setError(null)
    getAvailableTimes(id, format(selectedDate, 'yyyy-MM-dd'), isCaregiver ? { patientId: caregiverPatientId } : undefined)
      .then((r) => setAvailableSlots(r.items))
      .catch((e: unknown) => { setAvailableSlots([]); setError(e instanceof Error ? e.message : 'Failed to load times') })
      .finally(() => setLoadingSlots(false))
  }, [selectedDate, doctorId, isCaregiver, caregiverPatientId])

  function onCaregiverPatientChange(p: AssignedPatientRow | null) {
    setSelectedPatientLabel(p?.display_name ?? null)
  }

  async function handleBook(slot: AvailableTimeSlot) {
    const id = parseInt(doctorId, 10)
    setBookingSlot(slot.starts_at)
    setError(null)
    setSuccessMsg(null)
    try {
      const body: { doctor_id: number; starts_at: string; title?: string; patient_id?: number } = { doctor_id: id, starts_at: slot.starts_at }
      if (title.trim()) body.title = title.trim()
      if (isCaregiver) body.patient_id = Number(caregiverPatientId)
      await directBookAppointment(body)
      setAvailableSlots((prev) => prev.filter((s) => s.starts_at !== slot.starts_at))
      setSuccessMsg(`Booked for ${format(new Date(slot.starts_at), 'EEEE d MMM')} at ${format(new Date(slot.starts_at), 'HH:mm')}.`)
      setTimeout(() => setSuccessMsg(null), 6000)
      loadUpcoming()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Booking failed')
    } finally {
      setBookingSlot(null)
    }
  }

  async function handleCancel(apptId: number) {
    setError(null)
    try {
      await cancelAppointment(apptId)
      loadUpcoming()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cancel failed')
    }
  }

  function TimeSlotGroup({ label, slots }: { label: string; slots: AvailableTimeSlot[] }) {
    if (slots.length === 0) return null
    return (
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
        <div className="flex flex-wrap gap-2">
          {slots.map((slot) => {
            const isBooking = bookingSlot === slot.starts_at
            return (
              <button
                key={slot.starts_at}
                disabled={bookingSlot !== null}
                onClick={() => void handleBook(slot)}
                className={`h-9 min-w-[4.5rem] rounded-lg border px-3 text-sm font-medium transition-all
                  ${isBooking
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background hover:border-primary hover:bg-primary/5 hover:text-primary'
                  }
                  ${bookingSlot !== null && !isBooking ? 'cursor-not-allowed opacity-40' : ''}
                `}
              >
                {isBooking
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin mx-auto" />
                  : format(new Date(slot.starts_at), 'HH:mm')
                }
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <RoleGuard allowedRoles={['patient', 'caregiver']} title="Unavailable" description="Appointment booking is for patients and caregivers.">
      <div className="space-y-5 p-4 sm:p-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl flex items-center gap-2">
            <CalendarPlus className="h-7 w-7 text-primary shrink-0" />
            Book a Visit
          </h1>
          <p className="text-muted-foreground mt-1.5">
            {isCaregiver
              ? 'Select a linked patient, choose their doctor, and pick an available time.'
              : <>Pick a <Link href="/dashboard/care-circle" className="underline decoration-dotted hover:text-primary">linked doctor</Link>, choose a date, and reserve a slot.</>
            }
          </p>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive" role="alert">
            <X className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {successMsg && (
          <div className="rounded-md border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-3 py-2.5 text-sm text-green-700 dark:text-green-400">
            {successMsg}
          </div>
        )}

        {/* Caregiver patient picker */}
        {isCaregiver && (
          <Card>
            <CardContent className="pt-5">
              <DoctorPatientPicker
                id="appointments-caregiver-patient"
                value={caregiverPatientId}
                onChange={setCaregiverPatientId}
                onSelectedPatientChange={onCaregiverPatientChange}
                label="Linked patient"
                description="The visit is booked on their behalf."
              />
            </CardContent>
          </Card>
        )}

        {/* Two-column grid */}
        <div className="grid gap-5 lg:grid-cols-[1fr_340px] items-start">

          {/* ── Left: booking wizard ── */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>Schedule a visit</CardTitle>
              <CardDescription>Greyed-out dates have no available slots for the selected doctor.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">

              {!bookingContextReady ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Select a patient above to continue.
                </p>
              ) : loadingDoctors ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading care team…
                </div>
              ) : doctors.length === 0 ? (
                <div className="rounded-lg border border-dashed px-6 py-8 text-center space-y-1">
                  <Stethoscope className="h-8 w-8 mx-auto text-muted-foreground/50" />
                  <p className="text-sm font-medium text-muted-foreground mt-2">No linked doctors</p>
                  <p className="text-xs text-muted-foreground">
                    {isCaregiver
                      ? 'This patient has not linked any doctors yet.'
                      : <><Link href="/dashboard/care-circle" className="underline hover:text-primary">Add a doctor</Link> from Care Circle first.</>
                    }
                  </p>
                </div>
              ) : (
                <>
                  {/* Step 1 */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <StepBadge n={1} />
                      <span className="text-sm font-semibold">Doctor &amp; visit details</span>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground">Doctor</Label>
                        <Select value={doctorId} onValueChange={setDoctorId}>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select doctor" />
                          </SelectTrigger>
                          <SelectContent>
                            {doctors.map((d) => (
                              <SelectItem key={d.doctor_id} value={String(d.doctor_id)}>
                                {d.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {selectedDoctor?.specialization && (
                          <p className="text-xs text-muted-foreground">{selectedDoctor.specialization}</p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="appt-title" className="text-xs text-muted-foreground">Visit title (optional)</Label>
                        <Input
                          id="appt-title"
                          placeholder="e.g. Follow-up consultation"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <Separator />

                  {/* Step 2 */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <StepBadge n={2} />
                      <span className="text-sm font-semibold">Pick a date</span>
                    </div>
                    {loadingAvailability ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                        <Loader2 className="h-4 w-4 animate-spin" /> Loading schedule…
                      </div>
                    ) : doctorAvailability.length === 0 ? (
                      <div className="rounded-lg border border-dashed px-4 py-5 text-center">
                        <CalendarDays className="h-6 w-6 mx-auto text-muted-foreground/50 mb-1.5" />
                        <p className="text-sm text-muted-foreground">This doctor hasn&apos;t set their availability yet.</p>
                      </div>
                    ) : (
                      <div className="flex w-full justify-center overflow-x-auto py-1 sm:justify-start [&_[data-slot=calendar]]:min-w-fit">
                        <Calendar
                          mode="single"
                          selected={selectedDate}
                          onSelect={setSelectedDate}
                          disabled={isDateDisabled}
                          captionLayout="label"
                          fixedWeeks
                          className={cn(
                            'rounded-xl border border-border bg-muted/15 shadow-sm',
                            'p-4 sm:p-5',
                            /* Larger tap targets than default; scales nav + caption with cells */
                            '[--cell-size:2.875rem] min-[380px]:[--cell-size:3rem]',
                          )}
                          classNames={{
                            /* Must include flex-1 etc. — parent merges this over defaults */
                            weekday:
                              'text-muted-foreground rounded-md flex-1 select-none text-center font-medium text-[11px] uppercase tracking-wide sm:text-xs',
                          }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Step 3 */}
                  {selectedDate && (
                    <>
                      <Separator />
                      <div className="space-y-4">
                        <div className="flex items-center gap-2">
                          <StepBadge n={3} />
                          <span className="text-sm font-semibold">
                            Choose a time
                            <span className="ml-2 font-normal text-muted-foreground">
                              — {format(selectedDate, 'EEEE, MMMM d')}
                            </span>
                          </span>
                        </div>

                        {loadingSlots ? (
                          <div className="flex justify-center py-6 text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin" />
                          </div>
                        ) : availableSlots.length === 0 ? (
                          <div className="rounded-lg border border-dashed px-4 py-5 text-center">
                            <Clock className="h-6 w-6 mx-auto text-muted-foreground/50 mb-1.5" />
                            <p className="text-sm text-muted-foreground">No open slots on this date.</p>
                            <p className="text-xs text-muted-foreground mt-0.5">All times are booked — try another day.</p>
                          </div>
                        ) : (
                          <div className="space-y-4">
                            <TimeSlotGroup label="Morning" slots={morningSlots} />
                            <TimeSlotGroup label="Afternoon" slots={afternoonSlots} />
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* ── Right: upcoming visits ── */}
          <Card className="lg:sticky lg:top-6">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {isCaregiver && selectedPatientLabel ? `${selectedPatientLabel}'s visits` : 'Upcoming visits'}
                </CardTitle>
                {appointments.length > 0 && (
                  <Badge variant="secondary">{appointments.length}</Badge>
                )}
              </div>
              <CardDescription>Tap cancel if plans change.</CardDescription>
            </CardHeader>
            <CardContent>
              {isCaregiver && !caregiverPatientId ? (
                <p className="text-sm text-muted-foreground py-6 text-center">Select a patient to see their visits.</p>
              ) : loadingAppts ? (
                <div className="flex justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : appointments.length === 0 ? (
                <div className="py-8 text-center space-y-1">
                  <CalendarDays className="h-8 w-8 mx-auto text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground mt-2">No upcoming visits</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {appointments.map((a) => (
                    <li key={a.id} className="rounded-lg border bg-card p-3.5 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{a.title}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {format(new Date(a.starts_at), 'HH:mm')} – {format(new Date(a.ends_at), 'HH:mm')}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-xs shrink-0">
                          {relativeDay(a.starts_at)}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-xs text-muted-foreground space-y-0.5">
                          <p>{format(new Date(a.starts_at), 'EEE, d MMM yyyy')}</p>
                          <p className="flex items-center gap-1">
                            <Stethoscope className="h-3 w-3" />
                            {a.doctor_name}
                          </p>
                          {isCaregiver && <p>Patient: {a.patient_name}</p>}
                        </div>
                        <button
                          onClick={() => void handleCancel(a.id)}
                          className="text-xs text-muted-foreground hover:text-destructive transition-colors shrink-0"
                          aria-label="Cancel appointment"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

        </div>
      </div>
    </RoleGuard>
  )
}
