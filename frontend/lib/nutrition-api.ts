import { getApiUrls } from './auth'

const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

async function getJson<T>(path: string) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function postMultipart<T>(path: string, formData: FormData) {
  const { fastapi } = getApiUrls()
  // FastAPI endpoints are not prefixed with /api/v1 by default in this project
  const response = await fetch(`${fastapi}${path}`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function postJson<T>(path: string, body: any) {
  const response = await fetch(`${base()}${apiPrefix()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export type ExercisePlanRow = {
  id: number
  patient_id: number
  patient_username: string
  title: string
  intensity: 'low' | 'moderate' | 'high'
  duration_minutes: number
  scheduled_for: string
  status: 'planned' | 'completed' | 'skipped'
  notes: string
  recovery_plan: {
    snack_suggestion: string
    hydration_ml: number
    glucose_recheck_minutes: number
    next_session_tip: string
  } | null
}

export type NutritionAnalysisReport = {
  plat_identifie: string
  confiance_identification: string
  ingredients_detectes: {
    ingredient: string
    confiance_visuelle: number
    surface_pct: number
  }[]
  analyse_nutritionnelle: {
    summary: string
    dish_type: string
    ingredients_analysis: {
      ingredient: string
      gi: string
      benefit: string
      risk_for_diabetic: string
    }[]
    global_assessment: {
      total_calories: string
      total_glycemic_load: string
      risk_level: 'green' | 'orange' | 'red'
      explanation: string
    }
    recommendations: string[]
    healthy_alternatives: {
      replace: string
      with: string
      benefit: string
    }[]
  }
  temps_traitement_sec: number
}

export async function listExercisePlans(patientId?: string, limit = 20) {
  const query = new URLSearchParams({ limit: String(limit) })
  if (patientId) query.set('patient_id', patientId)
  return getJson<{ items: ExercisePlanRow[]; total: number }>(`/nutrition/exercise?${query.toString()}`)
}

export async function analyseNutritionPhoto(image: File, profile: any) {
  const formData = new FormData()
  formData.append('image', image)
  formData.append('profil', JSON.stringify(profile))
  return postMultipart<NutritionAnalysisReport>('/nutrition/analyse', formData)
}

// ── Weekly Meal Planner ───────────────────────────────────────────────────────

export type CuisineOption = 'mediterranean' | 'maghreb' | 'middle_eastern' | 'western'
export type GILevel = 'low' | 'medium' | 'high'

export interface MealItem {
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
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

export interface DayPlan {
  day_index: number
  day_name: string
  meals: MealItem[]
}

export interface WeekSummary {
  avg_daily_calories: number
  avg_daily_carbs_g: number
  avg_daily_protein_g: number
  avg_daily_fat_g: number
  dietary_philosophy: string
}

export interface WeeklyMealPlan {
  id: number
  week_start: string
  status: 'pending' | 'ready' | 'failed'
  cuisine: CuisineOption
  generated_at: string | null
  week_summary: WeekSummary
  days: DayPlan[]
}

export async function generateMealPlan(cuisine: CuisineOption = 'mediterranean'): Promise<WeeklyMealPlan> {
  return postJson<WeeklyMealPlan>('/nutrition/meal-plan/generate', { cuisine })
}

export async function getMealPlan(patientId?: string): Promise<WeeklyMealPlan | null> {
  const query = patientId ? `?patient_id=${patientId}` : ''
  try {
    return await getJson<WeeklyMealPlan>(`/nutrition/meal-plan/current${query}`)
  } catch {
    return null
  }
}

export async function regenerateMealPlanDay(planId: number, dayIndex: number): Promise<WeeklyMealPlan> {
  return postJson<WeeklyMealPlan>(`/nutrition/meal-plan/${planId}/regenerate-day`, { day_index: dayIndex })
}

