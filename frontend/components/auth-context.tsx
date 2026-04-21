'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { fetchCurrentSessionUser, AuthUser, getApiUrls } from '@/lib/auth'

interface AuthContextType {
  user: AuthUser | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const pathname = usePathname()

  const refreshUser = async () => {
    setLoading(true)
    const sessionUser = await fetchCurrentSessionUser()
    setUser(sessionUser)
    setLoading(false)
  }

  useEffect(() => {
    refreshUser()
  }, [])

  // Basic route protection
  useEffect(() => {
    if (!loading) {
      const isPublicPath = pathname === '/login' || pathname === '/signup' || pathname === '/'
      if (!user && !isPublicPath) {
        router.push(`/login?next=${pathname}`)
      } else if (user && isPublicPath && pathname !== '/') {
         // Redirect to dashboard if logged in and trying to access login/signup
         if (pathname === '/login' || pathname === '/signup') {
            router.push('/dashboard')
         }
      }
    }
  }, [user, loading, pathname, router])

  const login = async (username: string, password: string) => {
    setError(null)
    const { django } = getApiUrls()
    try {
      const res = await fetch(`${django}/api/auth/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      })
      if (!res.ok) {
        throw new Error('Invalid credentials')
      }
      await refreshUser()
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
      throw err
    }
  }

  const logout = async () => {
    const { django } = getApiUrls()
    try {
      const res = await fetch(`${django}/api/auth/logout/`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!res.ok) {
        // Avoid throwing from logout for server-side auth cleanup issues.
        console.warn('Logout endpoint responded with non-OK status:', res.status)
      }
    } catch (err) {
      // Network or CORS failures should not block local logout navigation.
      console.warn('Logout request failed:', err)
    } finally {
      setUser(null)
      router.push('/login')
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
