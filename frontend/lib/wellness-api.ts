const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${base()}${apiPrefix()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<T>
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${base()}${apiPrefix()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<T>
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type GILevel       = 'low' | 'medium' | 'high'
export type Intensity     = 'low' | 'moderate' | 'high'
export type ExerciseType  = 'cardio' | 'strength' | 'flexibility' | 'HIIT' | 'mobility'
export type MealType      = 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'pre_workout_snack' | 'post_workout_snack'
export type FitnessLevel  = 'beginner' | 'intermediate' | 'advanced'
export type FitnessGoal   = 'weight_loss' | 'muscle_gain' | 'endurance' | 'flexibility' | 'maintenance'
export type CuisineOption = 'mediterranean' | 'maghreb' | 'middle_eastern' | 'western'

export interface WellnessExerciseSession {
  id?: number
  exercise_type: ExerciseType | string
  name: string
  description: string
  intensity: Intensity
  duration_minutes: number
  sets?: number | null
  reps?: number | null
  equipment: string[]
  pre_exercise_glucose_check: boolean
  post_exercise_snack_tip: string
  diabetes_rationale: string
  status?: string
}

export interface WellnessMealItem {
  meal_type: MealType
  name: string
  description: string
  ingredients: string[]
  preparation_time_minutes: number
  calories_kcal: number
  carbs_g: number
  protein_g: number
  fat_g: number
  sugar_g: number
  glycemic_index: GILevel
  glycemic_load: GILevel
  diabetes_rationale: string
}

export interface WellnessDay {
  day_index: number
  day_name: string
  exercise_sessions: WellnessExerciseSession[]
  meals: WellnessMealItem[]
}

export interface WellnessWeekSummary {
  total_active_days?: number
  total_load_minutes?: number
  avg_intensity_score?: number
  fitness_philosophy?: string
  avg_daily_calories?: number
  avg_daily_carbs_g?: number
  avg_daily_protein_g?: number
  avg_daily_fat_g?: number
  dietary_philosophy?: string
}

export interface WeeklyWellnessPlan {
  id: number
  week_start: string
  status: 'pending' | 'ready' | 'failed'
  fitness_level: string
  goal: string
  cuisine: string
  generated_at: string | null
  week_summary: WellnessWeekSummary
  days: WellnessDay[]
}

export interface GenerateWellnessPlanOptions {
  cuisine?: CuisineOption
  fitness_level?: FitnessLevel
  goal?: FitnessGoal
  sessions_per_week?: number
  minutes_per_session?: number
  available_equipment?: string[]
  injuries_or_limits?: string[]
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function generateWellnessPlan(
  options: GenerateWellnessPlanOptions = {},
): Promise<WeeklyWellnessPlan> {
  return postJson<WeeklyWellnessPlan>('/nutrition/wellness-plan/generate', options)
}

export async function getWellnessPlan(patientId?: string): Promise<WeeklyWellnessPlan | null> {
  const query = patientId ? `?patient_id=${patientId}` : ''
  try {
    return await getJson<WeeklyWellnessPlan>(`/nutrition/wellness-plan/current${query}`)
  } catch {
    return null
  }
}

export async function regenerateWellnessDay(
  planId: number,
  dayIndex: number,
): Promise<WeeklyWellnessPlan> {
  return postJson<WeeklyWellnessPlan>(
    `/nutrition/wellness-plan/${planId}/regenerate-day`,
    { day_index: dayIndex },
  )
}
