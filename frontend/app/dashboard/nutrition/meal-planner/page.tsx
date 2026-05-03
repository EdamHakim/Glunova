'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  CalendarDays, ChefHat, RefreshCw, Sparkles, Utensils,
  Coffee, Sun, Moon, Apple, ChevronDown, ChevronUp, Info,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/components/auth-context'
import {
  type CuisineOption,
  type DayPlan,
  type GILevel,
  type MealItem,
  type NutritionalSource,
  type WeeklyMealPlan,
  generateMealPlan,
  getMealPlan,
  regenerateMealPlanDay,
} from '@/lib/nutrition-api'

// ── Constants ─────────────────────────────────────────────────────────────────

const CUISINE_LABELS: Record<CuisineOption, string> = {
  mediterranean:  'Mediterranean',
  maghreb:        'Maghreb / North African',
  middle_eastern: 'Middle Eastern',
  western:        'Western',
}

const MEAL_ICONS: Record<string, React.ReactNode> = {
  breakfast: <Coffee className="h-4 w-4" />,
  lunch:     <Sun    className="h-4 w-4" />,
  dinner:    <Moon   className="h-4 w-4" />,
  snack:     <Apple  className="h-4 w-4" />,
}

const GI_COLORS: Record<GILevel, string> = {
  low:    'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  medium: 'bg-amber-100  text-amber-800  dark:bg-amber-900/30  dark:text-amber-300',
  high:   'bg-red-100    text-red-800    dark:bg-red-900/30    dark:text-red-300',
}

// ── Sub-components ────────────────────────────────────────────────────────────

function NutritionalSourceBadge({ source }: { source: NutritionalSource }) {
  return source === 'usda_validated' ? (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 cursor-default">
            USDA ✓
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">Macros validated against USDA FoodData Central</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ) : (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 cursor-default">
            LLM est.
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">Macros are AI-estimated — USDA lookup returned no match for some ingredients</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function MealCard({ meal }: { meal: MealItem }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-lg border border-border bg-card p-3 space-y-2 text-sm">
      {/* Header row */}
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {MEAL_ICONS[meal.meal_type]}
        <span className="text-xs uppercase tracking-wide font-medium">{meal.meal_type}</span>
        <div className="ml-auto">
          <NutritionalSourceBadge source={meal.nutritional_source} />
        </div>
      </div>

      {/* Meal name */}
      <p className="font-semibold leading-snug">{meal.name}</p>
      <p className="text-xs text-muted-foreground leading-snug">{meal.description}</p>

      {/* Calorie + macro row */}
      <div className="flex flex-wrap gap-1.5 items-center">
        <Badge variant="secondary" className="text-xs font-medium">
          {Math.round(meal.calories_kcal)} kcal
        </Badge>
        <span className="text-xs text-muted-foreground">
          C&nbsp;{Math.round(meal.carbs_g)}g&nbsp;·&nbsp;
          P&nbsp;{Math.round(meal.protein_g)}g&nbsp;·&nbsp;
          F&nbsp;{Math.round(meal.fat_g)}g
        </span>
      </div>

      {/* GI / GL badges */}
      <div className="flex gap-1.5">
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${GI_COLORS[meal.glycemic_index]}`}>
          GI {meal.glycemic_index}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${GI_COLORS[meal.glycemic_load]}`}>
          GL {meal.glycemic_load}
        </span>
        <span className="text-[10px] text-muted-foreground ml-auto">
          ~{meal.preparation_time_minutes} min
        </span>
      </div>

      {/* Collapsible: rationale + ingredients */}
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <button className="flex items-center gap-1 text-xs text-primary hover:underline w-full text-left">
            {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {open ? 'Hide details' : 'Rationale & ingredients'}
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-2 pt-2">
          {/* Diabetes rationale */}
          <p className="text-xs text-muted-foreground italic leading-relaxed border-l-2 border-emerald-400 pl-2">
            {meal.diabetes_rationale}
          </p>
          {/* Ingredient list */}
          <ul className="space-y-0.5">
            {meal.ingredients.map((ing, i) => {
              const usdaEntry = meal.usda_breakdown.find((b) => b.ingredient === ing)
              return (
                <li key={i} className="flex items-start gap-1 text-xs text-muted-foreground">
                  <span className="mt-0.5 text-emerald-500">·</span>
                  <span>{ing}</span>
                  {usdaEntry?.usda_name && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3 w-3 text-muted-foreground/50 ml-auto flex-shrink-0 mt-0.5 cursor-default" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs font-medium">{usdaEntry.usda_name}</p>
                          {usdaEntry.calories_kcal !== undefined && (
                            <p className="text-xs">
                              {Math.round(usdaEntry.calories_kcal)} kcal ·&nbsp;
                              C {Math.round(usdaEntry.carbs_g ?? 0)}g ·&nbsp;
                              P {Math.round(usdaEntry.protein_g ?? 0)}g ·&nbsp;
                              F {Math.round(usdaEntry.fat_g ?? 0)}g
                            </p>
                          )}
                          {usdaEntry.usda_fdc_id && (
                            <p className="text-[10px] text-muted-foreground">FDC ID: {usdaEntry.usda_fdc_id}</p>
                          )}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </li>
              )
            })}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

function DayColumn({
  day,
  planId,
  isPatient,
  regenLoading,
  onRegenerate,
}: {
  day: DayPlan
  planId: number
  isPatient: boolean
  regenLoading: boolean
  onRegenerate: (dayIndex: number) => void
}) {
  const today = new Date()
  const weekStart = new Date(today)
  weekStart.setDate(today.getDate() - today.getDay() + 1)
  const dayDate = new Date(weekStart)
  dayDate.setDate(weekStart.getDate() + day.day_index)

  const isToday =
    dayDate.getDate() === today.getDate() &&
    dayDate.getMonth() === today.getMonth() &&
    dayDate.getFullYear() === today.getFullYear()

  return (
    <div className="flex flex-col gap-2 min-w-[220px]">
      {/* Day header */}
      <div
        className={`flex items-center justify-between px-2 py-1.5 rounded-lg ${
          isToday ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}
      >
        <div>
          <p className="font-semibold text-sm">{day.day_name.slice(0, 3)}</p>
          <p className={`text-xs ${isToday ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
            {dayDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
          </p>
        </div>
        {isPatient && (
          <Button
            size="icon"
            variant="ghost"
            className={`h-7 w-7 ${isToday ? 'hover:bg-primary-foreground/10' : ''}`}
            disabled={regenLoading}
            onClick={() => onRegenerate(day.day_index)}
            title="Regenerate this day"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${regenLoading ? 'animate-spin' : ''}`} />
          </Button>
        )}
      </div>

      {/* Meal cards */}
      {(['breakfast', 'lunch', 'dinner', 'snack'] as const).map((type) => {
        const meal = day.meals.find((m) => m.meal_type === type)
        return meal ? (
          <MealCard key={type} meal={meal} />
        ) : (
          <div key={type} className="rounded-lg border border-dashed border-border p-3 text-center">
            <p className="text-xs text-muted-foreground">{type}</p>
          </div>
        )
      })}
    </div>
  )
}

function WeekSummaryCard({ plan }: { plan: WeeklyMealPlan }) {
  const s = plan.week_summary
  if (!s) return null
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <p className="text-sm italic text-muted-foreground mb-3">{s.dietary_philosophy}</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Avg kcal/day',  value: Math.round(s.avg_daily_calories) },
            { label: 'Avg carbs/day', value: `${Math.round(s.avg_daily_carbs_g)}g` },
            { label: 'Avg protein',   value: `${Math.round(s.avg_daily_protein_g)}g` },
            { label: 'Avg fat',       value: `${Math.round(s.avg_daily_fat_g)}g` },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg bg-muted px-3 py-2 text-center">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-semibold text-sm mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function PlanSkeleton() {
  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex gap-3" style={{ minWidth: 'max-content' }}>
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="flex flex-col gap-2 min-w-[220px]">
            <Skeleton className="h-12 rounded-lg" />
            {Array.from({ length: 4 }).map((__, j) => (
              <Skeleton key={j} className="h-32 rounded-lg" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

interface MealPlannerProps {
  patientId?: string
  isPatient?: boolean
}

export function MealPlannerTabContent({ patientId, isPatient = false }: MealPlannerProps) {
  const [plan, setPlan]               = useState<WeeklyMealPlan | null>(null)
  const [cuisine, setCuisine]         = useState<CuisineOption>('mediterranean')
  const [generating, setGenerating]   = useState(false)
  const [regenDay, setRegenDay]       = useState<number | null>(null)
  const [error, setError]             = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)

  // Load existing plan on mount / patient change
  useEffect(() => {
    setInitialLoading(true)
    getMealPlan(patientId)
      .then((p) => {
        setPlan(p)
        if (p) setCuisine(p.cuisine)
      })
      .finally(() => setInitialLoading(false))
  }, [patientId])

  const handleGenerate = useCallback(async () => {
    setError(null)
    setGenerating(true)
    try {
      const newPlan = await generateMealPlan(cuisine)
      setPlan(newPlan)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed. Please try again.')
    } finally {
      setGenerating(false)
    }
  }, [cuisine])

  const handleRegenerateDay = useCallback(
    async (dayIndex: number) => {
      if (!plan) return
      setError(null)
      setRegenDay(dayIndex)
      try {
        const updated = await regenerateMealPlanDay(plan.id, dayIndex)
        setPlan(updated)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Day regeneration failed.')
      } finally {
        setRegenDay(null)
      }
    },
    [plan],
  )

  const weekLabel = (() => {
    const today = new Date()
    const mon = new Date(today)
    mon.setDate(today.getDate() - today.getDay() + 1)
    const sun = new Date(mon)
    sun.setDate(mon.getDate() + 6)
    return `Week of ${mon.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} – ${sun.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`
  })()

  return (
    <div className="space-y-4">
      {/* Control bar */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* Cuisine selector */}
            <div className="flex items-center gap-2">
              <ChefHat className="h-4 w-4 text-muted-foreground" />
              <Select
                value={cuisine}
                onValueChange={(v) => setCuisine(v as CuisineOption)}
                disabled={!isPatient || generating}
              >
                <SelectTrigger className="w-[200px] h-9 text-sm">
                  <SelectValue placeholder="Cuisine style" />
                </SelectTrigger>
                <SelectContent>
                  {(Object.entries(CUISINE_LABELS) as [CuisineOption, string][]).map(([val, label]) => (
                    <SelectItem key={val} value={val}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Generate button — patient only */}
            {isPatient && (
              <Button
                onClick={handleGenerate}
                disabled={generating}
                size="sm"
                className="gap-1.5"
              >
                {generating ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Generating…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    {plan ? 'Regenerate week' : 'Generate plan'}
                  </>
                )}
              </Button>
            )}

            {/* Week label */}
            <div className="ml-auto flex items-center gap-1.5 text-sm text-muted-foreground">
              <CalendarDays className="h-4 w-4" />
              {weekLabel}
            </div>
          </div>
          {!isPatient && (
            <p className="text-xs text-muted-foreground mt-2">
              Meal plan generation is reserved for patient accounts. You are viewing read-only.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Loading skeleton */}
      {(initialLoading || generating) && <PlanSkeleton />}

      {/* Week summary */}
      {!initialLoading && !generating && plan && (
        <WeekSummaryCard plan={plan} />
      )}

      {/* Weekly grid */}
      {!initialLoading && !generating && plan && (
        <div className="overflow-x-auto pb-4">
          <div className="flex gap-3" style={{ minWidth: 'max-content' }}>
            {plan.days.map((day) => (
              <DayColumn
                key={day.day_index}
                day={day}
                planId={plan.id}
                isPatient={isPatient}
                regenLoading={regenDay === day.day_index}
                onRegenerate={handleRegenerateDay}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!initialLoading && !generating && !plan && (
        <Card className="border-dashed">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Utensils className="h-6 w-6 text-muted-foreground" />
            </div>
            <CardTitle className="text-lg">No meal plan yet</CardTitle>
            <CardDescription>
              {isPatient
                ? 'Generate your personalised 7-day plan. Macros are cross-validated against USDA FoodData Central.'
                : 'This patient has not generated a meal plan yet.'}
            </CardDescription>
          </CardHeader>
          {isPatient && (
            <CardContent className="flex justify-center pb-6">
              <Button onClick={handleGenerate} disabled={generating} className="gap-1.5">
                <Sparkles className="h-4 w-4" />
                Generate my meal plan
              </Button>
            </CardContent>
          )}
        </Card>
      )}

      {/* Source legend */}
      {!initialLoading && !generating && plan && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
            USDA ✓ = macros validated from USDA FoodData Central
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />
            LLM est. = AI-estimated (USDA lookup found no match)
          </span>
        </div>
      )}
    </div>
  )
}

// Default export for Next.js route
export default function MealPlannerPage() {
  const { user } = useAuth()
  const isPatient = user?.role === 'patient'

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Weekly Meal Planner</h1>
        <p className="text-muted-foreground mt-2">
          {isPatient
            ? 'AI-generated 7-day plan tailored to your HbA1c, glucose levels, and medications. Macros validated against USDA.'
            : "Read-only view of the patient's personalised weekly meal plan."}
        </p>
      </div>
      <MealPlannerTabContent patientId={isPatient ? undefined : ''} isPatient={isPatient} />
    </div>
  )
}
