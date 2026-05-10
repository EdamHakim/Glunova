'use client'

import { useAuth } from '@/components/auth-context'
import { WellnessPlannerTabContent } from './wellness-planner-tab-content'

export default function WellnessPlannerPage() {
  const { user } = useAuth()
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Weekly Wellness Plan</h1>
        <p className="text-muted-foreground mt-2">
          AI-generated exercise and nutrition, calibrated to your diabetes profile.
        </p>
      </div>
      <WellnessPlannerTabContent
        patientId={user?.id}
        isPatient={user?.role === 'patient'}
      />
    </div>
  )
}
