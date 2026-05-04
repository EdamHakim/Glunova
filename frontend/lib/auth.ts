export type UserRole = 'patient' | 'doctor' | 'caregiver'

export type AuthUser = {
  username: string
  role: UserRole
  /** Django user primary key from JWT (`user_id` claim or verified from backend). */
  userId: number | null
  id: string // Add string ID for compatibility with documents-api
  full_name: string
  // Health profile fields (available for patients only — from PatientProfile)
  age?: number | null
  weight_kg?: number | null
  height_cm?: number | null
  diabetes_type?: string | null
  allergies?: string[] | null
  medication?: string[] | null
  last_glucose?: string | null
  carb_limit_per_meal_g?: number | null
  date_of_birth?: string | null
  gender?: string | null
  hypertension?: boolean | null
  heart_disease?: boolean | null
  smoking_status?: string | null
  hba1c_level?: number | null
  blood_glucose_level?: number | null
  profile_picture?: string | null
  email?: string
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

export async function fetchWithAuthRefresh(input: RequestInfo | URL, init: RequestInit = {}) {
  const requestInit: RequestInit = {
    ...init,
    credentials: init.credentials ?? 'include',
  }

  let response = await fetch(input, requestInit)
  if (response.status !== 401) return response

  const { django } = getApiUrls()
  const refreshResponse = await fetch(`${django}/api/auth/token/refresh/`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!refreshResponse.ok) return response

  response = await fetch(input, requestInit)
  return response
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
      allergies: data.allergies,
      medication: data.medication,
      last_glucose: data.last_glucose,
      carb_limit_per_meal_g: data.carb_limit_per_meal_g,
      date_of_birth: data.date_of_birth,
      gender: data.gender,
      hypertension: data.hypertension,
      heart_disease: data.heart_disease,
      smoking_status: data.smoking_status,
      hba1c_level: data.hba1c_level,
      blood_glucose_level: data.blood_glucose_level,
      profile_picture: data.profile_picture,
      email: data.email,
    }
  } catch {
    return null
  }
}

export async function updateUserProfile(data: Partial<AuthUser & {
  date_of_birth?: string,
  gender?: string,
  hypertension?: boolean,
  heart_disease?: boolean,
  smoking_status?: string,
  hba1c_level?: number,
  blood_glucose_level?: number,
  diabetes_type?: string,
  allergies?: string[],
}>) {
  try {
    const { django } = getApiUrls()
    const r = await fetch(`${django}/api/v1/users/me`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      credentials: 'include',
    })
    if (!r.ok) throw new Error(await r.text())
    return await r.json()
  } catch (err) {
    throw err
  }
}

export async function uploadProfilePicture(file: File) {
  const { django } = getApiUrls()
  const formData = new FormData()
  formData.append('profile_picture', file)
  const r = await fetch(`${django}/api/v1/users/me`, {
    method: 'PATCH',
    body: formData,
    credentials: 'include',
  })
  if (!r.ok) throw new Error(await r.text())
  return await r.json()
}

// Keeping legacy getCurrentUser for small parts of the app until refactor is complete
// but it will likely return null now since token is not readable.
export function getCurrentUser(): AuthUser | null {
  return null
}
