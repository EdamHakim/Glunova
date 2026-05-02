export type UserRole = 'patient' | 'doctor' | 'caregiver'

export type AuthUser = {
  username: string
  role: UserRole
  /** Django user primary key from JWT (`user_id` claim or verified from backend). */
  userId: number | null
  id: string // Add string ID for compatibility with documents-api
  full_name: string
  // Health profile fields (available for patients)
  age?: number | null
  weight_kg?: number | null
  height_cm?: number | null
  diabetes_type?: string | null
  medication?: string[] | null
  last_glucose?: string | null
  carb_limit_per_meal_g?: number | null
}

function resolveClientApiBaseUrl(envValue: string | undefined, port: number, fallback: string) {
  if (envValue && envValue.trim()) return envValue
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:${port}`
  }
  return fallback
}

export function getApiUrls() {
  return {
    django: resolveClientApiBaseUrl(process.env.NEXT_PUBLIC_DJANGO_API_URL, 8000, 'http://localhost:8000'),
    fastapi: resolveClientApiBaseUrl(process.env.NEXT_PUBLIC_FASTAPI_API_URL, 8001, 'http://localhost:8001'),
  }
}

// Cookies are handled by the browser automatically with credentials: 'include'.
export function setTokens(_access: string, _refresh: string) {
  // Logic removed as tokens are now in HttpOnly cookies set by backend.
}

export function getAccessToken(): string | null {
  // Cannot read HttpOnly access_token from JS.
  return null
}

export function clearTokens() {
  // Backend's /logout clears cookies.
}

/**
 * Fetches the current session user from the backend.
 * This is the new source of truth for "logged in" state.
 */
export async function fetchCurrentSessionUser(): Promise<AuthUser | null> {
  try {
    const { django } = getApiUrls()
    const r = await fetch(`${django}/api/v1/users/me`, {
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // Ensure cookies are sent
    })
    if (!r.ok) return null
    const data = await r.json()
    return {
      id: data.id,
      userId: Number(data.id),
      username: data.username || '',
      role: data.role as UserRole,
      full_name: data.full_name || '',
      age: data.age,
      weight_kg: data.weight_kg,
      height_cm: data.height_cm,
      diabetes_type: data.diabetes_type,
      medication: data.medication,
      last_glucose: data.last_glucose,
      carb_limit_per_meal_g: data.carb_limit_per_meal_g,
    }
  } catch {
    return null
  }
}

// Keeping legacy getCurrentUser for small parts of the app until refactor is complete
// but it will likely return null now since token is not readable.
export function getCurrentUser(): AuthUser | null {
  return null
}
