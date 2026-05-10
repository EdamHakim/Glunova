'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { format } from 'date-fns'
import { CalendarPlus, Loader2 } from 'lucide-react'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { AssignedPatientRow } from '@/lib/dashboard-api'
import {
  bookAppointment,
  cancelAppointment,
  listBookingDoctorsForPatient,
  listBookableSlots,
  listCareCircleAppointments,
  listMyDoctors,
  type BookableSlot,
  type CareCircleAppointment,
  type DoctorLink,
} from '@/lib/carecircle-api'

export default function AppointmentsPage() {
  const { user } = useAuth()
  const isCaregiver = user?.role === 'caregiver'
  const isPatient = user?.role === 'patient'

  const [caregiverPatientId, setCaregiverPatientId] = useState('')
  const [selectedPatientLabel, setSelectedPatientLabel] = useState<string | null>(null)

  const [doctors, setDoctors] = useState<DoctorLink[]>([])
  const [doctorId, setDoctorId] = useState<string>('')
  const [slots, setSlots] = useState<BookableSlot[]>([])
  const [appointments, setAppointments] = useState<CareCircleAppointment[]>([])
  const [title, setTitle] = useState('')
  const [loadingDoctors, setLoadingDoctors] = useState(true)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [loadingAppts, setLoadingAppts] = useState(true)
  const [bookingId, setBookingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const bookingContextReady = isPatient || (isCaregiver && caregiverPatientId !== '')

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
    setError(null)
    listMyDoctors()
      .then((r) => {
        setDoctors(r.items)
        if (r.items.length > 0) setDoctorId(String(r.items[0].doctor_id))
        else setDoctorId('')
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load doctors'))
      .finally(() => setLoadingDoctors(false))
  }, [isPatient])

  useEffect(() => {
    if (!isCaregiver) return
    if (!caregiverPatientId) {
      setDoctors([])
      setDoctorId('')
      setLoadingDoctors(false)
      return
    }
    setLoadingDoctors(true)
    setError(null)
    listBookingDoctorsForPatient(caregiverPatientId)
      .then((r) => {
        setDoctors(r.items)
        if (r.items.length > 0) setDoctorId(String(r.items[0].doctor_id))
        else setDoctorId('')
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load doctors'))
      .finally(() => setLoadingDoctors(false))
  }, [isCaregiver, caregiverPatientId])

  useEffect(() => {
    loadUpcoming()
  }, [loadUpcoming])

  useEffect(() => {
    const id = parseInt(doctorId, 10)
    if (!Number.isFinite(id) || !bookingContextReady) {
      setSlots([])
      return
    }
    setLoadingSlots(true)
    setError(null)
    const slotOpts = isCaregiver ? { patientId: caregiverPatientId } : undefined
    listBookableSlots(id, slotOpts)
      .then((r) => setSlots(r.items))
      .catch((e: unknown) => {
        setSlots([])
        setError(e instanceof Error ? e.message : 'Failed to load slots')
      })
      .finally(() => setLoadingSlots(false))
  }, [doctorId, bookingContextReady, isCaregiver, caregiverPatientId])

  function onCaregiverPatientChange(p: AssignedPatientRow | null) {
    setSelectedPatientLabel(p?.display_name ?? null)
  }

  async function handleBook(slot: BookableSlot) {
    setBookingId(slot.id)
    setError(null)
    try {
      const body: { slot_id: number; title?: string; patient_id?: number } = { slot_id: slot.id }
      if (title.trim()) body.title = title.trim()
      if (isCaregiver) body.patient_id = Number(caregiverPatientId)
      await bookAppointment(body)
      setSlots((prev) => prev.filter((s) => s.id !== slot.id))
      loadUpcoming()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Booking failed')
    } finally {
      setBookingId(null)
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

  return (
    <RoleGuard
      allowedRoles={['patient', 'caregiver']}
      title="Unavailable"
      description="Appointment booking is for patients and caregivers."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl flex items-center gap-2">
            <CalendarPlus className="h-8 w-8 text-primary shrink-0" />
            Book an appointment
          </h1>
          <p className="text-muted-foreground mt-2">
            {isCaregiver ? (
              <>
                Choose a linked patient, then one of their doctors and an open slot. You can also review this patient&apos;s
                schedule in{' '}
                <Link href="/dashboard/care-circle" className="underline font-medium hover:text-primary">
                  Care Circle
                </Link>
                .
              </>
            ) : (
              <>
                Choose a{' '}
                <Link href="/dashboard/care-circle" className="underline font-medium hover:text-primary">
                  linked doctor
                </Link>{' '}
                and reserve an available slot they published.
              </>
            )}
          </p>
        </div>

        {error ? (
          <p className="text-sm text-destructive whitespace-pre-wrap" role="alert">
            {error}
          </p>
        ) : null}

        {isCaregiver ? (
          <Card>
            <CardHeader>
              <CardTitle>Patient</CardTitle>
              <CardDescription>Select who this visit is for. Only patients you are linked to as a caregiver appear here.</CardDescription>
            </CardHeader>
            <CardContent>
              <DoctorPatientPicker
                id="appointments-caregiver-patient"
                value={caregiverPatientId}
                onChange={setCaregiverPatientId}
                onSelectedPatientChange={onCaregiverPatientChange}
                label="Linked patient"
                description="Search by name — the visit is booked on their behalf."
              />
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Available openings</CardTitle>
            <CardDescription>Shown times use your browser&apos;s timezone; the clinic sees the same instant in coordinated universal time.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!bookingContextReady ? (
              <p className="text-sm text-muted-foreground">
                {isCaregiver ? 'Select a patient above to load their doctors and open slots.' : 'Loading…'}
              </p>
            ) : loadingDoctors ? (
              <p className="text-sm text-muted-foreground">Loading care team…</p>
            ) : doctors.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {isCaregiver ? (
                  <>
                    This patient has no linked doctors yet. They can add doctors under{' '}
                    <Link href="/dashboard/care-circle" className="underline font-medium hover:text-primary">
                      Care Circle
                    </Link>
                    .
                  </>
                ) : (
                  <>
                    You have no linked doctors yet.{' '}
                    <Link href="/dashboard/care-circle" className="underline font-medium hover:text-primary">
                      Add one under Care Circle
                    </Link>
                    .
                  </>
                )}
              </p>
            ) : (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Doctor</Label>
                    <Select value={doctorId} onValueChange={setDoctorId}>
                      <SelectTrigger className="w-full min-w-48">
                        <SelectValue placeholder="Doctor" />
                      </SelectTrigger>
                      <SelectContent>
                        {doctors.map((d) => (
                          <SelectItem key={d.doctor_id} value={String(d.doctor_id)}>
                            {d.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="appt-title">Visit title (optional)</Label>
                    <Input id="appt-title" placeholder="Consultation" value={title} onChange={(e) => setTitle(e.target.value)} />
                  </div>
                </div>

                {loadingSlots ? (
                  <div className="flex justify-center py-10 text-muted-foreground">
                    <Loader2 className="h-8 w-8 animate-spin" />
                  </div>
                ) : slots.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 border border-dashed rounded-lg px-4 text-center">
                    This doctor has no open upcoming slots right now.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {slots.map((slot) => (
                      <li
                        key={slot.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm"
                      >
                        <div>
                          <div className="font-medium">{format(new Date(slot.starts_at), 'PPpp')}</div>
                          <div className="text-xs text-muted-foreground">Ends {format(new Date(slot.ends_at), 'p')}</div>
                        </div>
                        <Button
                          size="sm"
                          disabled={bookingId !== null}
                          onClick={() => void handleBook(slot)}
                          className="shrink-0"
                        >
                          {bookingId === slot.id ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Booking…
                            </>
                          ) : (
                            'Reserve'
                          )}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              {isCaregiver
                ? selectedPatientLabel
                  ? `${selectedPatientLabel}'s upcoming visits`
                  : 'Upcoming visits'
                : 'Your upcoming visits'}
            </CardTitle>
            <CardDescription>Cancel if plans change; the opening returns to the doctor&apos;s pool.</CardDescription>
          </CardHeader>
          <CardContent>
            {isCaregiver && !caregiverPatientId ? (
              <p className="text-sm text-muted-foreground py-6 text-center">Select a patient to see their scheduled visits.</p>
            ) : loadingAppts ? (
              <p className="text-sm text-muted-foreground py-6 text-center">Loading…</p>
            ) : appointments.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No upcoming scheduled visits.</p>
            ) : (
              <ul className="space-y-2">
                {appointments.map((a) => (
                  <li
                    key={a.id}
                    className="flex flex-wrap items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm"
                  >
                    <div>
                      <div className="font-medium">{a.title}</div>
                      <div className="text-muted-foreground">{format(new Date(a.starts_at), 'PPpp')}</div>
                      <div className="text-xs text-muted-foreground mt-1">With {a.doctor_name}</div>
                      {isCaregiver ? (
                        <div className="text-xs text-muted-foreground mt-0.5">Patient: {a.patient_name}</div>
                      ) : null}
                    </div>
                    <Button variant="outline" size="sm" className="shrink-0" onClick={() => void handleCancel(a.id)}>
                      Cancel
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}
