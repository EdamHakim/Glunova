export type UserRole = 'patient' | 'doctor' | 'caregiver'

export type AuthUser = {
  username: string
  role: UserRole
}

const ACCESS_TOKEN_KEY = 'glunova_access_token'
const REFRESH_TOKEN_KEY = 'glunova_refresh_token'

export function getApiUrls() {
  return {
    django: process.env.NEXT_PUBLIC_DJANGO_API_URL ?? 'http://localhost:8000',
    fastapi: process.env.NEXT_PUBLIC_FASTAPI_API_URL ?? 'http://localhost:8001',
  }
}

export function setTokens(access: string, refresh: string) {
  if (typeof window === 'undefined') return
  localStorage.setItem(ACCESS_TOKEN_KEY, access)
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function clearTokens() {
  if (typeof window === 'undefined') return
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

function parseJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(atob(parts[1]))
    return payload
  } catch {
    return null
  }
}

export function getCurrentUser(): AuthUser | null {
  const token = getAccessToken()
  if (!token) return null
  const payload = parseJwtPayload(token)
  if (!payload) return null
  const username = typeof payload.username === 'string' ? payload.username : ''
  const role = typeof payload.role === 'string' ? (payload.role as UserRole) : 'patient'
  if (!username) return null
  return { username, role }
}
