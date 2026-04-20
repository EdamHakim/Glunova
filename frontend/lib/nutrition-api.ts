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

export type NutritionSummary = {
  totals: { calories_kcal: number; carbs_g: number; sugar_g: number }
  goal: {
    target_calories_kcal: number
    target_carbs_g: number
    target_protein_g: number
    target_fat_g: number
    target_sugar_g: number
    valid_from: string
    valid_to: string | null
  } | null
  averages: { gi: number; gl: number }
  substitutions_count: number
}

export type MealLogRow = {
  id: number
  patient_id: number
  patient_username: string
  input_type: 'text' | 'barcode' | 'voice' | 'photo'
  description: string
  carbs_g: number
  calories_kcal: number
  sugar_g: number
  gi: number
  gl: number
  logged_at: string
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

export async function getNutritionSummary(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
  return getJson<NutritionSummary>(`/nutrition/summary${query}`)
}

export async function listNutritionMeals(patientId?: string, limit = 20) {
  const query = new URLSearchParams({ limit: String(limit) })
  if (patientId) query.set('patient_id', patientId)
  return getJson<{ items: MealLogRow[]; total: number }>(`/nutrition/meals?${query.toString()}`)
}

export async function listExercisePlans(patientId?: string, limit = 20) {
  const query = new URLSearchParams({ limit: String(limit) })
  if (patientId) query.set('patient_id', patientId)
  return getJson<{ items: ExercisePlanRow[]; total: number }>(`/nutrition/exercise?${query.toString()}`)
}
