import type { AuthUser } from '@/lib/auth'

/** Prefer full name, then username — never exposes numeric IDs. */
export function sessionUserDisplayName(
  user: Pick<AuthUser, 'full_name' | 'username'> | null | undefined,
): string {
  if (!user) return ''
  const name = typeof user.full_name === 'string' ? user.full_name.trim() : ''
  if (name) return name
  const login = typeof user.username === 'string' ? user.username.trim() : ''
  return login
}
