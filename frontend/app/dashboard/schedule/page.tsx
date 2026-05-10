'use client'

import { addWeeks, eachDayOfInterval, format, isBefore, startOfToday } from 'date-fns'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarClock, ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'
import RoleGuard from '@/components/auth/role-guard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  bulkCreateAppointmentSlots,
  createAppointmentSlot,
  deleteAppointmentSlot,
  listMyAppointmentSlots,
  type DoctorAppointmentSlot,
} from '@/lib/carecircle-api'

// Mon=0 … Sun=6 (internal index). Maps to Date.getDay(): Mon→1 … Sun→0
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const DAY_GET_DAY = [1, 2, 3, 4, 5, 6, 0]

function parseTimeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0)
}

function minutesToTimeStr(min: number): string {
  return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
}

function combineDateTime(date: Date, timeStr: string): Date {
  const [h, m] = timeStr.split(':').map(Number)
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), h ?? 0, m ?? 0, 0, 0)
}

interface TemplateConfig {
  selectedDays: boolean[]
  workStart: string
  workEnd: string
  hasLunch: boolean
  lunchStart: string
  lunchEnd: string
  durationMin: number
  rangeFrom: Date
  rangeTo: Date
}

function buildSlotPreviews(cfg: TemplateConfig): { starts_at: string; ends_at: string }[] {
  if (isBefore(cfg.rangeTo, cfg.rangeFrom)) return []
  const result: { starts_at: string; ends_at: string }[] = []
  for (const day of eachDayOfInterval({ start: cfg.rangeFrom, end: cfg.rangeTo })) {
    const dayIdx = DAY_GET_DAY.indexOf(day.getDay())
    if (dayIdx === -1 || !cfg.selectedDays[dayIdx]) continue
    const blocks: [number, number][] = cfg.hasLunch
      ? [
          [parseTimeToMinutes(cfg.workStart), parseTimeToMinutes(cfg.lunchStart)],
          [parseTimeToMinutes(cfg.lunchEnd), parseTimeToMinutes(cfg.workEnd)],
        ]
      : [[parseTimeToMinutes(cfg.workStart), parseTimeToMinutes(cfg.workEnd)]]
    for (const [blockStart, blockEnd] of blocks) {
      let t = blockStart
      while (t + cfg.durationMin <= blockEnd) {
        const start = combineDateTime(day, minutesToTimeStr(t))
        result.push({
          starts_at: start.toISOString(),
          ends_at: new Date(start.getTime() + cfg.durationMin * 60_000).toISOString(),
        })
        t += cfg.durationMin
      }
    }
  }
  return result
}

function groupByDate(slots: DoctorAppointmentSlot[]): Map<string, DoctorAppointmentSlot[]> {
  const map = new Map<string, DoctorAppointmentSlot[]>()
  for (const slot of slots) {
    const key = format(new Date(slot.starts_at), 'yyyy-MM-dd')
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(slot)
  }
  return map
}

export default function DoctorSchedulePage() {
  const [slots, setSlots] = useState<DoctorAppointmentSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Template state
  const [selectedDays, setSelectedDays] = useState([true, true, true, true, true, false, false])
  const [workStart, setWorkStart] = useState('09:00')
  const [workEnd, setWorkEnd] = useState('17:00')
  const [hasLunch, setHasLunch] = useState(true)
  const [lunchStart, setLunchStart] = useState('12:00')
  const [lunchEnd, setLunchEnd] = useState('13:00')
  const [durationMin, setDurationMin] = useState('30')
  const [rangeFrom, setRangeFrom] = useState<Date>(startOfToday())
  const [rangeTo, setRangeTo] = useState<Date>(addWeeks(startOfToday(), 4))
  const [generating, setGenerating] = useState(false)

  // Single slot state
  const [showSingleForm, setShowSingleForm] = useState(false)
  const [singleDate, setSingleDate] = useState<Date | undefined>()
  const [singleStart, setSingleStart] = useState('09:00')
  const [singleDuration, setSingleDuration] = useState('30')
  const [addingOne, setAddingOne] = useState(false)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    listMyAppointmentSlots()
      .then((r) => setSlots(r.items))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load slots'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { reload() }, [reload])

  const preview = useMemo(
    () =>
      buildSlotPreviews({
        selectedDays,
        workStart,
        workEnd,
        hasLunch,
        lunchStart,
        lunchEnd,
        durationMin: parseInt(durationMin, 10) || 30,
        rangeFrom,
        rangeTo,
      }),
    [selectedDays, workStart, workEnd, hasLunch, lunchStart, lunchEnd, durationMin, rangeFrom, rangeTo],
  )

  const grouped = useMemo(() => groupByDate(slots), [slots])
  const dateKeys = useMemo(() => Array.from(grouped.keys()).sort(), [grouped])

  function flash(msg: string) {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(null), 4000)
  }

  async function handleGenerate() {
    if (preview.length === 0) { setError('No slots to generate. Check your configuration.'); return }
    setGenerating(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const result = await bulkCreateAppointmentSlots(preview)
      flash(`Created ${result.created} slot${result.created !== 1 ? 's' : ''}${result.skipped ? ` · ${result.skipped} overlapping skipped` : ''}.`)
      reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate slots')
    } finally {
      setGenerating(false)
    }
  }

  async function handleAddOne(ev: React.FormEvent) {
    ev.preventDefault()
    if (!singleDate) { setError('Pick a date first.'); return }
    const mins = parseInt(singleDuration, 10) || 30
    const start = combineDateTime(singleDate, singleStart)
    const end = new Date(start.getTime() + mins * 60_000)
    setAddingOne(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const created = await createAppointmentSlot({ starts_at: start.toISOString(), ends_at: end.toISOString() })
      setSlots((prev) => [...prev, created].sort((a, b) => a.starts_at.localeCompare(b.starts_at)))
      flash('Slot added.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not add slot')
    } finally {
      setAddingOne(false)
    }
  }

  async function handleDelete(id: number) {
    setError(null)
    setSuccessMsg(null)
    try {
      await deleteAppointmentSlot(id)
      setSlots((prev) => prev.filter((s) => s.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove slot')
    }
  }

  const openCount = slots.filter((s) => !s.is_booked).length
  const bookedCount = slots.filter((s) => s.is_booked).length

  return (
    <RoleGuard allowedRoles={['doctor']} title="Unavailable" description="Only doctors can manage appointment availability.">
      <div className="space-y-6 p-4 sm:p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl flex items-center gap-2">
            <CalendarClock className="h-8 w-8 text-primary shrink-0" />
            Appointment Availability
          </h1>
          <p className="text-muted-foreground mt-2">
            Define your weekly schedule and publish all slots at once for patients to book.
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive whitespace-pre-wrap rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2" role="alert">
            {error}
          </p>
        )}
        {successMsg && (
          <p className="text-sm text-green-700 dark:text-green-400 rounded-md border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-3 py-2">
            {successMsg}
          </p>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          {/* ── Left column ── */}
          <div className="space-y-4">
            {/* Weekly template */}
            <Card>
              <CardHeader>
                <CardTitle>Weekly schedule</CardTitle>
                <CardDescription>
                  Set your recurring working hours and generate all slots at once.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Day toggles */}
                <div className="space-y-2">
                  <Label>Working days</Label>
                  <div className="flex gap-1.5">
                    {DAY_LABELS.map((day, i) => (
                      <button
                        key={day}
                        type="button"
                        onClick={() =>
                          setSelectedDays((prev) => prev.map((v, idx) => (idx === i ? !v : v)))
                        }
                        className={`h-9 w-11 rounded-md text-sm font-medium border transition-colors ${
                          selectedDays[i]
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-background text-muted-foreground border-border hover:border-primary/60 hover:text-foreground'
                        }`}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Working hours */}
                <div className="space-y-2">
                  <Label>Working hours</Label>
                  <div className="flex items-center gap-3">
                    <Input
                      type="time"
                      value={workStart}
                      onChange={(e) => setWorkStart(e.target.value)}
                      className="w-32"
                    />
                    <span className="text-muted-foreground text-sm">to</span>
                    <Input
                      type="time"
                      value={workEnd}
                      onChange={(e) => setWorkEnd(e.target.value)}
                      className="w-32"
                    />
                  </div>
                </div>

                {/* Lunch break */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="lunch-toggle"
                      checked={hasLunch}
                      onChange={(e) => setHasLunch(e.target.checked)}
                      className="h-4 w-4 rounded border-border accent-primary"
                    />
                    <Label htmlFor="lunch-toggle" className="cursor-pointer font-normal">
                      Lunch break
                    </Label>
                  </div>
                  {hasLunch && (
                    <div className="flex items-center gap-3 pl-6">
                      <Input
                        type="time"
                        value={lunchStart}
                        onChange={(e) => setLunchStart(e.target.value)}
                        className="w-32"
                      />
                      <span className="text-muted-foreground text-sm">to</span>
                      <Input
                        type="time"
                        value={lunchEnd}
                        onChange={(e) => setLunchEnd(e.target.value)}
                        className="w-32"
                      />
                    </div>
                  )}
                </div>

                {/* Slot duration */}
                <div className="space-y-2">
                  <Label>Slot duration</Label>
                  <Select value={durationMin} onValueChange={setDurationMin}>
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="15">15 min</SelectItem>
                      <SelectItem value="20">20 min</SelectItem>
                      <SelectItem value="30">30 min</SelectItem>
                      <SelectItem value="45">45 min</SelectItem>
                      <SelectItem value="60">60 min</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Date range */}
                <div className="space-y-2">
                  <Label>Date range</Label>
                  <div className="flex flex-wrap items-center gap-3">
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" type="button" className="w-36 justify-start text-left font-normal text-sm">
                          {format(rangeFrom, 'dd MMM yyyy')}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={rangeFrom}
                          onSelect={(d) => d && setRangeFrom(d)}
                          disabled={{ before: startOfToday() }}
                        />
                      </PopoverContent>
                    </Popover>
                    <span className="text-muted-foreground text-sm">to</span>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" type="button" className="w-36 justify-start text-left font-normal text-sm">
                          {format(rangeTo, 'dd MMM yyyy')}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={rangeTo}
                          onSelect={(d) => d && setRangeTo(d)}
                          disabled={{ before: rangeFrom }}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>

                {/* Preview + generate */}
                <div className="rounded-lg border bg-muted/40 px-4 py-3 space-y-3">
                  {preview.length > 0 ? (
                    <p className="text-sm text-muted-foreground">
                      <span className="font-semibold text-foreground text-base">{preview.length}</span>{' '}
                      slots will be published · overlapping ones are skipped automatically
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No slots in current configuration.
                    </p>
                  )}
                  <Button
                    onClick={handleGenerate}
                    disabled={generating || preview.length === 0}
                    className="w-full"
                  >
                    {generating ? 'Generating…' : `Generate ${preview.length > 0 ? preview.length + ' ' : ''}slots`}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Single slot adder (collapsible) */}
            <Card>
              <CardHeader className="pb-3">
                <button
                  type="button"
                  className="flex items-center justify-between w-full text-left"
                  onClick={() => setShowSingleForm((v) => !v)}
                >
                  <CardTitle className="text-base flex items-center gap-2">
                    <Plus className="h-4 w-4" />
                    Add a single slot
                  </CardTitle>
                  {showSingleForm ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
              </CardHeader>
              {showSingleForm && (
                <CardContent>
                  <form onSubmit={handleAddOne} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Date</Label>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button variant="outline" type="button" className="w-full justify-start text-left font-normal">
                            {singleDate ? format(singleDate, 'PPP') : 'Pick a date'}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={singleDate}
                            onSelect={setSingleDate}
                            disabled={{ before: startOfToday() }}
                          />
                        </PopoverContent>
                      </Popover>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Start time</Label>
                        <Input
                          type="time"
                          value={singleStart}
                          onChange={(e) => setSingleStart(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Duration</Label>
                        <Select value={singleDuration} onValueChange={setSingleDuration}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="15">15 min</SelectItem>
                            <SelectItem value="30">30 min</SelectItem>
                            <SelectItem value="45">45 min</SelectItem>
                            <SelectItem value="60">60 min</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <Button type="submit" variant="outline" disabled={addingOne || !singleDate} className="w-full">
                      {addingOne ? 'Adding…' : 'Add slot'}
                    </Button>
                  </form>
                </CardContent>
              )}
            </Card>
          </div>

          {/* ── Right column: slot list ── */}
          <Card>
            <CardHeader>
              <CardTitle>Your schedule</CardTitle>
              <CardDescription className="flex items-center gap-3">
                <span>{openCount} open</span>
                <span className="text-border">·</span>
                <span>{bookedCount} booked</span>
                <span className="text-border">·</span>
                <span>{slots.length} total</span>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-muted-foreground py-12 text-center">Loading…</p>
              ) : dateKeys.length === 0 ? (
                <div className="py-12 text-center space-y-1">
                  <p className="text-sm font-medium text-muted-foreground">No slots published yet</p>
                  <p className="text-xs text-muted-foreground/70">
                    Use the weekly schedule to generate your availability in one click.
                  </p>
                </div>
              ) : (
                <div className="space-y-5 max-h-[600px] overflow-y-auto pr-1">
                  {dateKeys.map((key) => {
                    const daySlots = grouped.get(key)!
                    return (
                      <div key={key}>
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                          {format(new Date(key + 'T12:00:00'), 'EEE, dd MMM yyyy')}
                        </p>
                        <ul className="space-y-1.5">
                          {daySlots.map((slot) => (
                            <li
                              key={slot.id}
                              className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="text-sm font-medium tabular-nums">
                                  {format(new Date(slot.starts_at), 'HH:mm')}
                                  {' – '}
                                  {format(new Date(slot.ends_at), 'HH:mm')}
                                </span>
                                <Badge
                                  variant={slot.is_booked ? 'default' : 'outline'}
                                  className="text-xs shrink-0"
                                >
                                  {slot.is_booked ? 'Booked' : 'Open'}
                                </Badge>
                              </div>
                              {!slot.is_booked && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="shrink-0 h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                  onClick={() => void handleDelete(slot.id)}
                                  aria-label="Delete slot"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </RoleGuard>
  )
}
