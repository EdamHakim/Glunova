'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'

const CataractDetectionPanel = dynamic(
  () => import('@/components/screening').then((m) => ({ default: m.CataractDetectionPanel })),
  {
    loading: () => (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
        Loading cataract screening…
      </div>
    ),
    ssr: false,
  },
)

export default function CataractDetectionPage() {
  const { user, loading } = useAuth()
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

  if (loading || !isClient) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  return (
    <RoleGuard
      allowedRoles={['patient', 'doctor']}
      title="Cataract Detection unavailable"
      description="Cataract detection screening is limited to authenticated users."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex items-center gap-2">
          <Link prefetch={false} href="/dashboard/screening">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Cataract Detection</h1>
            <p className="text-muted-foreground mt-1">
              AI-assisted cataract severity assessment from eye images
            </p>
          </div>
        </div>

        <CataractDetectionPanel />

        {/* Information Panel */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-2">How to Use</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Take a clear image of the eye</li>
              <li>• Upload the image using the upload area</li>
              <li>• Click &quot;Analyze Image&quot; to run detection</li>
              <li>• View detailed results and probabilities</li>
            </ul>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <h3 className="font-semibold text-amber-900 mb-2">Severity Grades</h3>
            <ul className="text-sm text-amber-800 space-y-1">
              <li>• <strong>Grade 0:</strong> No cataract detected</li>
              <li>• <strong>Grade 1:</strong> Early cataract present</li>
              <li>• <strong>Grade 2:</strong> Moderate cataract</li>
              <li>• <strong>Grade 3:</strong> Severe cataract</li>
            </ul>
          </div>
        </div>
      </div>
    </RoleGuard>
  )
}
