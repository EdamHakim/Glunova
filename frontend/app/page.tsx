'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/components/auth-context'

export default function Home() {
  const router = useRouter()
  const { user, loading } = useAuth()

  useEffect(() => {
    if (!loading) {
      if (user) {
        const landingPage = user.role === 'doctor' ? '/dashboard' : '/dashboard/monitoring'
        router.push(landingPage)
      } else {
        router.push('/login')
      }
    }
  }, [user, loading, router])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  )
}
