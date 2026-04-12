'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    router.push('/dashboard')
  }, [router])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Card className="w-96">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <div className="h-12 w-12 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold text-2xl mb-4">
            G
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Glunova AI Platform</h1>
          <p className="text-muted-foreground text-center mt-2">Initializing your dashboard...</p>
          <Spinner className="mt-6" />
        </CardContent>
      </Card>
    </div>
  )
}
