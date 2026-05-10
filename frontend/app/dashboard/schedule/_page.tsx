'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarClock, Save } from 'lucide-react'
import { useTranslations } from 'next-intl'
import RoleGuard from '@/components/auth/role-guard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { getMyAvailability, saveMyAvailability } from '@/lib/carecircle-api'

interface DayRow {
  active: boolean
  startTime: string
  endTime: string
}

const DEFAULT_ROWS: DayRow[] = Array.from({ length: 7 }, (_, i) => ({
  active: i < 5,
  startTime: '09:00',
  endTime: '17:00',
}))

function parseMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0)
}

export default function DoctorSchedulePage() {
  const t = useTranslations('schedule')
  const [rows, setRows] = useState<DayRow[]>(DEFAULT_ROWS)
  const [slotDuration, setSlotDuration] = useState('30')
  const [hasLunch, setHasLunch] = useState(true)
  const [lunchStart, setLunchStart] = useState('12:00')
  const [lunchEnd, setLunchEnd] = useState('13:00')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const DAY_LABELS = [t('days.0'), t('days.1'), t('days.2'), t('days.3'), t('days.4'), t('days.5'), t('days.6')]
  const DAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getMyAvailability()
      .then(({ items }) => {
        if (items.length === 0) return
        const next = DEFAULT_ROWS.map((r) => ({ ...r, active: false }))
        items.forEach((a) => {
          next[a.day_of_week] = { active: true, startTime: a.start_time, endTime: a.end_time }
        })
        setRows(next)
        setSlotDuration(String(items[0].slot_duration_min))
        if (items[0].lunch_start) {
          setHasLunch(true)
          setLunchStart(items[0].lunch_start)
          setLunchEnd(items[0].lunch_end ?? '13:00')
        } else {
          setHasLunch(false)
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load availability'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function updateRow(i: number, patch: Partial<DayRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await saveMyAvailability({
        schedule: rows
          .map((r, i) => (r.active ? { day_of_week: i, start_time: r.startTime, end_time: r.endTime } : null))
          .filter(Boolean) as { day_of_week: number; start_time: string; end_time: string }[],
        slot_duration_min: parseInt(slotDuration, 10) || 30,
        lunch_start: hasLunch ? lunchStart : null,
        lunch_end: hasLunch ? lunchEnd : null,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 4000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save availability')
    } finally {
      setSaving(false)
    }
  }

  const stats = useMemo(() => {
    const dur = parseInt(slotDuration, 10) || 30
    const lunchMins = hasLunch ? Math.max(0, parseMinutes(lunchEnd) - parseMinutes(lunchStart)) : 0
    const activeRows = rows.filter((r) => r.active)
    const dailySlots = activeRows.map((r) =>
      Math.floor(Math.max(0, parseMinutes(r.endTime) - parseMinutes(r.startTime) - lunchMins) / dur),
    )
    const totalSlots = dailySlots.reduce((s, n) => s + n, 0)
    const avgSlots = activeRows.length > 0 ? Math.round(totalSlots / activeRows.length) : 0
    return { daysCount: activeRows.length, totalSlots, avgSlots }
  }, [rows, slotDuration, hasLunch, lunchStart, lunchEnd])

  return (
    <RoleGuard
      allowedRoles={['doctor']}
      title={t('unavailableTitle')}
      description={t('unavailableDesc')}
    >
      <div className="space-y-6 p-4 sm:p-6">

        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl flex items-center gap-2">
            <CalendarClock className="h-7 w-7 text-primary shrink-0" />
            {t('weeklyAvailability')}
          </h1>
          <p className="text-muted-foreground mt-1.5">{t('availabilityDesc')}</p>
        </div>

        {error && (
          <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2" role="alert">
            {error}
          </p>
        )}
        {saved && (
          <p className="text-sm text-green-700 dark:text-green-400 rounded-md border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-3 py-2">
            {t('savedSuccess')}
          </p>
        )}

        {loading ? (
          <p className="text-sm text-muted-foreground py-16 text-center">{t('saving').replace('…', '')}</p>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[280px_1fr]">

            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('settingsCard')}</CardTitle>
                  <CardDescription>{t('appliedToAllDays')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>{t('slotDurationLabel')}</Label>
                    <Select value={slotDuration} onValueChange={setSlotDuration}>
                      <SelectTrigger className="w-full">
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

                  <Separator />

                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="lunch-toggle"
                        checked={hasLunch}
                        onChange={(e) => setHasLunch(e.target.checked)}
                        className="h-4 w-4 rounded border-border accent-primary"
                      />
                      <Label htmlFor="lunch-toggle" className="cursor-pointer font-normal">
                        {t('lunchBreak')}
                      </Label>
                    </div>
                    {hasLunch && (
                      <div className="grid grid-cols-2 gap-2 pl-6">
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">{t('from')}</p>
                          <Input
                            type="time"
                            value={lunchStart}
                            onChange={(e) => setLunchStart(e.target.value)}
                            className="h-8 text-sm"
                          />
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">{t('to')}</p>
                          <Input
                            type="time"
                            value={lunchEnd}
                            onChange={(e) => setLunchEnd(e.target.value)}
                            className="h-8 text-sm"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-muted/30">
                <CardContent className="pt-5 space-y-3">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                    {t('weeklyPreview')}
                  </p>
                  <div className="space-y-2.5">
                    {[
                      { label: t('activeDaysLabel'), value: `${stats.daysCount} / 7` },
                      { label: t('avgSlotsPerDay'), value: String(stats.avgSlots) },
                      { label: t('totalSlotsPerWeek'), value: String(stats.totalSlots), highlight: true },
                    ].map(({ label, value, highlight }) => (
                      <div key={label} className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">{label}</span>
                        <span className={`text-sm font-semibold tabular-nums ${highlight ? 'text-primary' : 'text-foreground'}`}>
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Button onClick={handleSave} disabled={saving} className="w-full" size="lg">
                <Save className="h-4 w-4 mr-2" />
                {saving ? t('saving') : t('saveAvailability')}
              </Button>
            </div>

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{t('workingDays')}</CardTitle>
                    <CardDescription className="mt-1">{t('toggleWorkingHours')}</CardDescription>
                  </div>
                  <Badge variant={stats.daysCount > 0 ? 'default' : 'outline'} className="shrink-0">
                    {t('activeCount', { count: stats.daysCount })}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {rows.map((row, i) => (
                    <div
                      key={DAY_LABELS[i]}
                      className={`flex items-center gap-3 px-6 py-3.5 transition-colors ${
                        row.active ? 'bg-background' : 'bg-muted/20'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => updateRow(i, { active: !row.active })}
                        className={`w-12 h-8 rounded-md text-xs font-bold shrink-0 border transition-all duration-150 ${
                          row.active
                            ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                            : 'bg-background text-muted-foreground border-border hover:border-muted-foreground/50'
                        }`}
                      >
                        {DAY_SHORT[i]}
                      </button>

                      <span
                        className={`w-24 shrink-0 text-sm select-none transition-colors ${
                          row.active ? 'font-medium text-foreground' : 'text-muted-foreground'
                        }`}
                      >
                        {DAY_LABELS[i]}
                      </span>

                      {row.active ? (
                        <div className="flex items-center gap-2 flex-1">
                          <Input
                            type="time"
                            value={row.startTime}
                            onChange={(e) => updateRow(i, { startTime: e.target.value })}
                            className="w-28 h-8 text-sm"
                          />
                          <span className="text-muted-foreground text-sm select-none">–</span>
                          <Input
                            type="time"
                            value={row.endTime}
                            onChange={(e) => updateRow(i, { endTime: e.target.value })}
                            className="w-28 h-8 text-sm"
                          />
                          <span className="text-xs text-muted-foreground ml-auto tabular-nums">
                            {Math.floor(
                              Math.max(
                                0,
                                parseMinutes(row.endTime) -
                                  parseMinutes(row.startTime) -
                                  (hasLunch ? Math.max(0, parseMinutes(lunchEnd) - parseMinutes(lunchStart)) : 0),
                              ) / (parseInt(slotDuration, 10) || 30),
                            )}{' '}
                            {t('slots')}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground/60 italic flex-1">{t('off')}</span>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

          </div>
        )}
      </div>
    </RoleGuard>
  )
}
