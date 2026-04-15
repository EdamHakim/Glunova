export type UserRole = 'patient' | 'doctor' | 'caregiver'

export type AuthUser = {
  username: string
  role: UserRole
  /** Django user primary key from JWT (`user_id` claim or verified from backend). */
  userId: number | null
  id: string // Add string ID for compatibility with documents-api
  full_name: string
}

export function getApiUrls() {
  return {
    django: process.env.NEXT_PUBLIC_DJANGO_API_URL ?? 'http://localhost:8000',
    fastapi: process.env.NEXT_PUBLIC_FASTAPI_API_URL ?? 'http://localhost:8001',
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
