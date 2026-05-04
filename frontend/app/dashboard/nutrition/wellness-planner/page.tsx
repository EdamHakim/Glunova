'use client'

import { useEffect, useState } from 'react'
import { addDays, format, parseISO } from 'date-fns'
import {
  Activity, AlertTriangle, Apple, ChevronDown, ChevronRight,
  Clock, Dumbbell, Flame, Loader2, Moon, Package, RefreshCw, Settings2,
  ShieldAlert, Sparkles, Timer, Zap,
} from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/components/auth-context'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  type CuisineOption,
  type FitnessGoal,
  type FitnessLevel,
  type WeeklyWellnessPlan,
  type WellnessDay,
  type WellnessExerciseSession,
  type WellnessMealItem,
  generateWellnessPlan,
  getWellnessPlan,
  regenerateWellnessDay,
} from '@/lib/wellness-api'
import { MealPhoto } from '@/components/nutrition/meal-photo'
import { ExerciseGif, SetTracker } from '@/components/nutrition/exercise-visual'
import { cn } from '@/lib/utils'

// ── Helpers ───────────────────────────────────────────────────────────────────

const dayDate = (weekStart: string, idx: number) =>
  format(addDays(parseISO(weekStart), idx), 'MMM d')

const intensityColor = (i: string) =>
  i === 'high'     ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  : i === 'moderate' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
  : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'

const exerciseTypeColor = (t: string) => {
  const m: Record<string, string> = {
    cardio:      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    strength:    'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    HIIT:        'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    flexibility: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    mobility:    'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  }
  return m[t] ?? 'bg-muted text-muted-foreground'
}

const mealTypeColor = (t: string) => {
  const m: Record<string, string> = {
    breakfast:           'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    lunch:               'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    dinner:              'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
    snack:               'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    pre_workout_snack:   'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
    post_workout_snack:  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  }
  return m[t] ?? 'bg-muted text-muted-foreground'
}

const mealTypeLabel = (t: string) =>
  t === 'pre_workout_snack'  ? 'Pre-Workout' :
  t === 'post_workout_snack' ? 'Post-Workout' :
  t.charAt(0).toUpperCase() + t.slice(1)

const giColor = (g: string) =>
  g === 'low' ? 'text-green-600 dark:text-green-400' :
  g === 'medium' ? 'text-amber-600 dark:text-amber-400' :
  'text-red-600 dark:text-red-400'

const EQUIPMENT_OPTIONS = [
  { id: 'none',             label: 'No equipment' },
  { id: 'dumbbells',        label: 'Dumbbells' },
  { id: 'resistance_bands', label: 'Resistance bands' },
  { id: 'yoga_mat',         label: 'Yoga mat' },
  { id: 'pull_up_bar',      label: 'Pull-up bar' },
  { id: 'gym',              label: 'Full gym access' },
]

// ── Generate Sheet ─────────────────────────────────────────────────────────────

function GenerateSheet({
  open, onOpenChange, onGenerate, generating,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onGenerate: (opts: {
    cuisine: CuisineOption
    fitness_level: FitnessLevel
    goal: FitnessGoal
    sessions_per_week: number
    minutes_per_session: number
    available_equipment: string[]
    injuries_or_limits: string[]
  }) => void
  generating: boolean
}) {
  const [cuisine, setCuisine]               = useState<CuisineOption>('mediterranean')
  const [fitnessLevel, setFitnessLevel]     = useState<FitnessLevel>('beginner')
  const [goal, setGoal]                     = useState<FitnessGoal>('maintenance')
  const [sessionsPerWeek, setSessionsPerWeek]   = useState(3)
  const [minutesPerSession, setMinutesPerSession] = useState(30)
  const [equipment, setEquipment]           = useState<string[]>(['none'])
  const [injuriesText, setInjuriesText]     = useState('')

  const toggleEquipment = (id: string) =>
    setEquipment(prev =>
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev.filter(e => e !== 'none'), id].filter(Boolean) || ['none'],
    )

  const handleSubmit = () =>
    onGenerate({
      cuisine,
      fitness_level: fitnessLevel,
      goal,
      sessions_per_week: sessionsPerWeek,
      minutes_per_session: minutesPerSession,
      available_equipment: equipment.length ? equipment : ['none'],
      injuries_or_limits: injuriesText
        ? injuriesText.split(',').map(s => s.trim()).filter(Boolean)
        : [],
    })

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex h-full w-full max-w-none flex-col gap-0 border-l border-border/80 p-0 sm:max-w-lg">
        <SheetHeader className="shrink-0 space-y-2 border-b bg-linear-to-br from-muted/60 to-muted/20 px-6 py-6 text-left">
          <SheetTitle className="flex items-center gap-2.5 pr-8 text-xl font-semibold tracking-tight">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/20">
              <Sparkles className="h-5 w-5" />
            </span>
            Generate wellness plan
          </SheetTitle>
          <SheetDescription className="text-sm leading-relaxed text-muted-foreground">
            Tune meals and workouts for the week. We use your diabetes profile from your account when building the plan.
          </SheetDescription>
        </SheetHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          <div className="space-y-8">
            {/* Nutrition */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-700 dark:text-amber-400">
                  <Apple className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold leading-none">Nutrition</h3>
                  <p className="mt-1 text-xs text-muted-foreground">Cuisine style for suggested meals</p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="wellness-cuisine" className="text-xs font-medium text-muted-foreground">
                  Cuisine style
                </Label>
                <Select value={cuisine} onValueChange={v => setCuisine(v as CuisineOption)}>
                  <SelectTrigger id="wellness-cuisine" className="h-11 bg-background">
                    <SelectValue placeholder="Choose cuisine" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mediterranean">Mediterranean</SelectItem>
                    <SelectItem value="maghreb">Maghreb / North African</SelectItem>
                    <SelectItem value="middle_eastern">Middle Eastern</SelectItem>
                    <SelectItem value="western">Western</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </section>

            <Separator />

            {/* Training */}
            <section className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Dumbbell className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold leading-none">Training</h3>
                  <p className="mt-1 text-xs text-muted-foreground">Level, goal, and weekly volume</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wellness-level" className="text-xs font-medium text-muted-foreground">
                    Fitness level
                  </Label>
                  <Select value={fitnessLevel} onValueChange={v => setFitnessLevel(v as FitnessLevel)}>
                    <SelectTrigger id="wellness-level" className="h-11 bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="beginner">Beginner</SelectItem>
                      <SelectItem value="intermediate">Intermediate</SelectItem>
                      <SelectItem value="advanced">Advanced</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wellness-goal" className="text-xs font-medium text-muted-foreground">
                    Primary goal
                  </Label>
                  <Select value={goal} onValueChange={v => setGoal(v as FitnessGoal)}>
                    <SelectTrigger id="wellness-goal" className="h-11 bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="weight_loss">Weight loss</SelectItem>
                      <SelectItem value="muscle_gain">Muscle gain</SelectItem>
                      <SelectItem value="endurance">Endurance</SelectItem>
                      <SelectItem value="flexibility">Flexibility</SelectItem>
                      <SelectItem value="maintenance">Maintenance</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wellness-sessions" className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Activity className="h-3 w-3" />
                    Sessions / week
                  </Label>
                  <Input
                    id="wellness-sessions"
                    type="number"
                    min={1}
                    max={7}
                    className="h-11 bg-background"
                    value={sessionsPerWeek}
                    onChange={e => setSessionsPerWeek(Number(e.target.value))}
                  />
                  <p className="text-[11px] text-muted-foreground">1–7 workout days</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wellness-minutes" className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Timer className="h-3 w-3" />
                    Minutes / session
                  </Label>
                  <Input
                    id="wellness-minutes"
                    type="number"
                    min={10}
                    max={120}
                    step={5}
                    className="h-11 bg-background"
                    value={minutesPerSession}
                    onChange={e => setMinutesPerSession(Number(e.target.value))}
                  />
                  <p className="text-[11px] text-muted-foreground">10–120 minutes</p>
                </div>
              </div>
            </section>

            <Separator />

            {/* Equipment */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/10 text-sky-700 dark:text-sky-400">
                  <Package className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold leading-none">Equipment</h3>
                  <p className="mt-1 text-xs text-muted-foreground">What you have access to this week</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {EQUIPMENT_OPTIONS.map(opt => {
                  const checked = equipment.includes(opt.id)
                  const inputId = `wellness-eq-${opt.id}`
                  return (
                    <label
                      key={opt.id}
                      htmlFor={inputId}
                      className={cn(
                        'flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 transition-all',
                        checked
                          ? 'border-primary/45 bg-primary/6 shadow-sm ring-1 ring-primary/15'
                          : 'border-border bg-card/80 hover:border-muted-foreground/25 hover:bg-muted/30',
                      )}
                    >
                      <Checkbox
                        id={inputId}
                        checked={checked}
                        onCheckedChange={() => toggleEquipment(opt.id)}
                        className="shrink-0"
                      />
                      <span className="text-sm font-medium leading-snug">{opt.label}</span>
                    </label>
                  )
                })}
              </div>
            </section>

            <Separator />

            {/* Safety */}
            <section className="space-y-3 rounded-xl border border-amber-500/25 bg-amber-500/6 p-4 dark:bg-amber-500/10">
              <div className="flex items-start gap-2.5">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
                <div className="min-w-0 space-y-1">
                  <h3 className="text-sm font-semibold text-foreground">Injuries & limits</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Optional. Separate with commas so the model can avoid risky movements.
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="wellness-injuries" className="sr-only">
                  Injuries and limits
                </Label>
                <Input
                  id="wellness-injuries"
                  placeholder="e.g. knee pain, no jumping, lower back sensitivity"
                  className="h-11 border-amber-500/20 bg-background/90"
                  value={injuriesText}
                  onChange={e => setInjuriesText(e.target.value)}
                />
              </div>
            </section>
          </div>
        </div>

        <SheetFooter className="shrink-0 gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur supports-backdrop-filter:bg-background/80">
          <p className="text-center text-[11px] text-muted-foreground leading-relaxed">
            Generation runs on the server and usually takes <span className="font-medium text-foreground">about a minute</span>.
            You can close this panel after starting — refresh the page if the plan does not appear.
          </p>
          <Button
            className="h-11 w-full text-base font-semibold shadow-md shadow-primary/15"
            size="lg"
            onClick={handleSubmit}
            disabled={generating}
          >
            {generating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating plan…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Generate weekly plan
              </>
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

// ── Day Column (week scroll) ───────────────────────────────────────────────────

function DayColumn({
  day, weekStart, selected, regenLoading,
  onSelect, onRegen,
}: {
  day: WellnessDay
  weekStart: string
  selected: boolean
  regenLoading: boolean
  onSelect: () => void
  onRegen: () => void
}) {
  const isRest   = !day.exercise_sessions || day.exercise_sessions.length === 0
  const totalKcal = day.meals.reduce((s, m) => s + m.calories_kcal, 0)
  const topSession = day.exercise_sessions[0]

  return (
    <div
      onClick={onSelect}
      className={`w-52 shrink-0 rounded-xl border cursor-pointer transition-all ${
        selected
          ? 'border-primary bg-primary/5 shadow-md'
          : 'border-border bg-card hover:border-primary/40 hover:shadow-sm'
      }`}
    >
      {/* Header */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-0.5">
          <p className="font-semibold text-sm">{day.day_name}</p>
          <button
            onClick={e => { e.stopPropagation(); onRegen() }}
            disabled={regenLoading}
            className="text-muted-foreground hover:text-primary transition-colors p-0.5 rounded"
            title="Regenerate this day"
          >
            {regenLoading
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <RefreshCw className="h-3.5 w-3.5" />}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">{dayDate(weekStart, day.day_index)}</p>
      </div>

      <div className="p-3 space-y-2.5">
        {/* Rest / Active badge */}
        {isRest ? (
          <div className="flex items-center gap-1.5">
            <Moon className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium">Rest day</span>
          </div>
        ) : (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs font-medium text-primary">{day.exercise_sessions.length} session{day.exercise_sessions.length > 1 ? 's' : ''}</span>
            </div>
            {topSession && (
              <div className="space-y-1">
                <p className="text-xs font-medium truncate">{topSession.name}</p>
                <div className="flex gap-1 flex-wrap">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${exerciseTypeColor(topSession.exercise_type)}`}>
                    {topSession.exercise_type}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${intensityColor(topSession.intensity)}`}>
                    {topSession.intensity}
                  </span>
                </div>
                {topSession.pre_exercise_glucose_check && (
                  <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <Zap className="h-3 w-3" />
                    <span className="text-[10px] font-medium">Glucose check</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Meal summary */}
        <div className="flex items-center gap-1.5">
          <Apple className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">{day.meals.length} meals</span>
        </div>
        {totalKcal > 0 && (
          <p className="text-xs font-semibold">{Math.round(totalKcal).toLocaleString()} kcal</p>
        )}

        {/* Expand cue */}
        <div className="flex items-center justify-end pt-0.5">
          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
            Details <ChevronRight className="h-3 w-3" />
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Exercise session card ──────────────────────────────────────────────────────

function SessionCard({ s }: { s: WellnessExerciseSession }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      {/* Animated exercise GIF + how-to steps */}
      <ExerciseGif name={s.name} exerciseType={s.exercise_type} />

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <p className="font-medium text-sm">{s.name}</p>
          <p className="text-xs text-muted-foreground">{s.description}</p>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${exerciseTypeColor(s.exercise_type)}`}>
          {s.exercise_type}
        </span>
      </div>

      {/* Duration + intensity */}
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{s.duration_minutes} min</span>
        <span className={`flex items-center gap-1 font-medium ${intensityColor(s.intensity)} px-1.5 py-0.5 rounded-full`}>
          <Flame className="h-3 w-3" />{s.intensity}
        </span>
      </div>

      {/* Interactive set tracker */}
      {s.sets && s.sets > 0 && (
        <SetTracker sets={s.sets} reps={s.reps} />
      )}

      {/* Equipment */}
      {s.equipment?.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {s.equipment.map(e => (
            <span key={e} className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{e}</span>
          ))}
        </div>
      )}

      {/* Glucose check warning */}
      {s.pre_exercise_glucose_check && (
        <div className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-3 py-2">
          <Zap className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
          <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">Check glucose before starting</p>
        </div>
      )}

      {/* Post-workout snack tip */}
      {s.post_exercise_snack_tip && (
        <p className="text-xs text-muted-foreground border-l-2 border-primary/40 pl-2">{s.post_exercise_snack_tip}</p>
      )}

      {/* Diabetes rationale */}
      {s.diabetes_rationale && (
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-xs text-primary hover:underline">
            Why this session <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">{s.diabetes_rationale}</p>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}

// ── Meal card ─────────────────────────────────────────────────────────────────

function MealCard({ m }: { m: WellnessMealItem }) {
  const [open, setOpen] = useState(false)
  const totalMacros = m.carbs_g + m.protein_g + m.fat_g || 1

  return (
    <div className="rounded-lg border border-border bg-card p-3 space-y-3 min-w-0 overflow-hidden">
      <MealPhoto name={m.name} />
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5">
          <p className="font-medium text-sm">{m.name}</p>
          <p className="text-xs text-muted-foreground">{m.description}</p>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${mealTypeColor(m.meal_type)}`}>
          {mealTypeLabel(m.meal_type)}
        </span>
      </div>

      {/* Macro bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">{Math.round(m.calories_kcal)} kcal</span>
          <span className={`font-medium ${giColor(m.glycemic_index)}`}>GI {m.glycemic_index}</span>
        </div>
        <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
          <div className="bg-amber-400" style={{ width: `${(m.carbs_g / totalMacros) * 100}%` }} />
          <div className="bg-blue-400"  style={{ width: `${(m.protein_g / totalMacros) * 100}%` }} />
          <div className="bg-rose-400"  style={{ width: `${(m.fat_g / totalMacros) * 100}%` }} />
        </div>
        <div className="flex gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-amber-400" />C {Math.round(m.carbs_g)}g</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-blue-400"  />P {Math.round(m.protein_g)}g</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-rose-400"  />F {Math.round(m.fat_g)}g</span>
        </div>
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger className="flex items-center gap-1 text-xs text-primary hover:underline">
          Ingredients & rationale <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-2 mt-2">
          <div className="flex flex-wrap gap-1">
            {m.ingredients.map((ing, i) => (
              <span key={i} className="text-[10px] bg-muted px-2 py-0.5 rounded-full text-muted-foreground">{ing}</span>
            ))}
          </div>
          {m.diabetes_rationale && (
            <p className="text-xs text-muted-foreground border-l-2 border-primary/40 pl-2 leading-relaxed">
              {m.diabetes_rationale}
            </p>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

// ── Day detail panel ──────────────────────────────────────────────────────────

function DayDetail({ day }: { day: WellnessDay }) {
  const isRest = !day.exercise_sessions || day.exercise_sessions.length === 0
  const glucoseReminders = day.meals
    .flatMap(m => (m.meal_type === 'pre_workout_snack' ? ['Check glucose before workout'] : []))

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {day.day_name}
            {isRest && <span className="ml-2 text-xs font-normal text-muted-foreground">— Rest day</span>}
          </CardTitle>
          {glucoseReminders.length > 0 && (
            <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-3 py-1 rounded-full">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span className="text-xs font-medium">Glucose monitoring day</span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue={isRest ? 'meals' : 'exercise'}>
          <TabsList className="mb-4">
            <TabsTrigger value="exercise" className="flex items-center gap-1.5">
              <Dumbbell className="h-3.5 w-3.5" />Exercise
              {!isRest && <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{day.exercise_sessions.length}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="meals" className="flex items-center gap-1.5">
              <Apple className="h-3.5 w-3.5" />Meals
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{day.meals.length}</Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="exercise">
            {isRest ? (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <Moon className="h-10 w-10 text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium">Rest day</p>
                <p className="text-xs text-muted-foreground mt-1">No exercise scheduled — focus on recovery and nutrition.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {day.exercise_sessions.map((s, i) => <SessionCard key={i} s={s} />)}
              </div>
            )}
          </TabsContent>

          <TabsContent value="meals">
            {day.meals.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No meals generated for this day.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {day.meals.map((m, i) => <MealCard key={i} m={m} />)}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

// ── Week summary bar ──────────────────────────────────────────────────────────

function WeekSummaryBar({ plan }: { plan: WeeklyWellnessPlan }) {
  const s = plan.week_summary
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: 'Active days',    value: s.total_active_days    ?? '—', icon: Activity },
        { label: 'Exercise load',  value: s.total_load_minutes ? `${s.total_load_minutes} min` : '—', icon: Clock },
        { label: 'Avg calories',   value: s.avg_daily_calories  ? `${Math.round(s.avg_daily_calories)} kcal` : '—', icon: Flame },
        { label: 'Avg carbs/day',  value: s.avg_daily_carbs_g   ? `${Math.round(s.avg_daily_carbs_g)}g` : '—', icon: Apple },
      ].map(({ label, value, icon: Icon }) => (
        <div key={label} className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <Icon className="h-4 w-4" />
            <span className="text-xs">{label}</span>
          </div>
          <p className="text-lg font-bold">{value}</p>
        </div>
      ))}
    </div>
  )
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function WellnessSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="w-52 h-52 shrink-0 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── Generating overlay ────────────────────────────────────────────────────────

function GeneratingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 space-y-4">
      <div className="relative">
        <Sparkles className="h-12 w-12 text-primary/30" />
        <Loader2 className="h-6 w-6 text-primary animate-spin absolute top-3 left-3" />
      </div>
      <div className="text-center space-y-1">
        <p className="font-medium">Generating your wellness plan…</p>
        <p className="text-sm text-muted-foreground">Building exercise schedule then calibrating meals to each day's load. This takes ~60 seconds.</p>
      </div>
      <Progress value={undefined} className="w-48 h-1" />
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function WellnessPlannerTabContent({
  patientId, isPatient,
}: {
  patientId?: string
  isPatient: boolean
}) {
  const { user } = useAuth()
  const [plan, setPlan]           = useState<WeeklyWellnessPlan | null>(null)
  const [loading, setLoading]     = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedDay, setSelectedDay] = useState(0)
  const [regenDay, setRegenDay]   = useState<number | null>(null)
  const [showSheet, setShowSheet] = useState(false)

  const pid = patientId || user?.id

  useEffect(() => {
    if (!pid) { setLoading(false); return }
    setLoading(true)
    getWellnessPlan(String(pid)).then(setPlan).finally(() => setLoading(false))
  }, [pid])

  const handleGenerate = async (opts: Parameters<typeof generateWellnessPlan>[0]) => {
    setGenerating(true)
    setShowSheet(false)
    try {
      const newPlan = await generateWellnessPlan(opts)
      setPlan(newPlan)
      setSelectedDay(0)
      toast.success('Wellness plan ready!')
    } catch (e) {
      toast.error('Generation failed: ' + (e instanceof Error ? e.message : 'unknown error'))
    } finally {
      setGenerating(false)
    }
  }

  const handleRegenDay = async (dayIdx: number) => {
    if (!plan) return
    setRegenDay(dayIdx)
    try {
      const updated = await regenerateWellnessDay(plan.id, dayIdx)
      setPlan(updated)
      toast.success(`${updated.days[dayIdx]?.day_name} regenerated`)
    } catch (e) {
      toast.error('Regeneration failed')
    } finally {
      setRegenDay(null)
    }
  }

  const selectedDayData = plan?.days.find(d => d.day_index === selectedDay) ?? plan?.days[0]

  if (loading) return <WellnessSkeleton />
  if (generating) return <GeneratingState />

  return (
    <div className="space-y-5">
      {/* Actions row */}
      <div className="flex items-center justify-between gap-3">
        <div>
          {plan ? (
            <p className="text-xs text-muted-foreground">
              Week of <span className="font-medium">{plan.week_start}</span>
              {' · '}<span className="capitalize">{plan.fitness_level}</span>
              {' · '}<span className="capitalize">{plan.goal.replace(/_/g, ' ')}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">No plan generated yet.</p>
          )}
        </div>
        <div className="flex gap-2">
          {plan && (
            <Button variant="outline" size="sm" onClick={() => setShowSheet(true)}>
              <Settings2 className="h-4 w-4 mr-1.5" />Regenerate
            </Button>
          )}
          {(!plan || !generating) && (
            <Button size="sm" onClick={() => setShowSheet(true)} disabled={!isPatient}>
              <Sparkles className="h-4 w-4 mr-1.5" />
              {plan ? 'New plan' : 'Generate plan'}
            </Button>
          )}
        </div>
      </div>

      {!isPatient && !plan && (
        <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground text-center">
          Wellness plan generation is available for patient accounts only.
        </div>
      )}

      {plan && (
        <>
          <WeekSummaryBar plan={plan} />

          {/* Week summary text */}
          {(plan.week_summary.fitness_philosophy || plan.week_summary.dietary_philosophy) && (
            <p className="text-xs text-muted-foreground italic leading-relaxed">
              {plan.week_summary.fitness_philosophy}{' '}
              {plan.week_summary.dietary_philosophy}
            </p>
          )}

          {/* Horizontal week scroll */}
          <div className="overflow-x-auto pb-2 -mx-1 px-1">
            <div className="flex gap-3 min-w-max">
              {plan.days.map(day => (
                <DayColumn
                  key={day.day_index}
                  day={day}
                  weekStart={plan.week_start}
                  selected={selectedDay === day.day_index}
                  regenLoading={regenDay === day.day_index}
                  onSelect={() => setSelectedDay(day.day_index)}
                  onRegen={() => handleRegenDay(day.day_index)}
                />
              ))}
            </div>
          </div>

          {/* Selected day detail */}
          {selectedDayData && <DayDetail day={selectedDayData} />}
        </>
      )}

      <GenerateSheet
        open={showSheet}
        onOpenChange={setShowSheet}
        onGenerate={handleGenerate}
        generating={generating}
      />
    </div>
  )
}

// ── Standalone page ───────────────────────────────────────────────────────────

export default function WellnessPlannerPage() {
  const { user } = useAuth()
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Weekly Wellness Plan</h1>
        <p className="text-muted-foreground mt-2">
          AI-generated exercise and nutrition, calibrated to your diabetes profile.
        </p>
      </div>
      <WellnessPlannerTabContent
        patientId={user?.id}
        isPatient={user?.role === 'patient'}
      />
    </div>
  )
}
