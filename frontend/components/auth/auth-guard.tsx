'use client'

import React from 'react'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/components/auth-context'

type AuthGuardProps = {
  children: React.ReactNode
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner />
      </div>
    )
  }

  if (!user) {
    // Redirection is handled by AuthProvider's useEffect, 
    // but we return null here to avoid rendering children.
    return null
  }

  return <>{children}</>
}
