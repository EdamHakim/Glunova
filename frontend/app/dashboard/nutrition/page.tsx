'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NutritionAnalysisModal } from '@/components/nutrition/nutrition-analysis-modal'
import { MealPlannerTabContent } from './meal-planner/page'
import { WellnessPlannerTabContent } from './wellness-planner/page'

export default function NutritionPage() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const role = user?.role
  const isPatient = role === 'patient'
  const isDoctor = role === 'doctor'
  const canAssistLogging = role === 'caregiver'
  const intro = isDoctor
    ? 'Review nutrition plans and food analysis for assigned patients.'
    : canAssistLogging
      ? 'Support AI food analysis and view wellness plans for linked patients.'
      : 'Analyze meals with AI and manage your weekly nutrition and wellness plan.'

  useEffect(() => {
    if (user?.role === 'patient') setPatientId(user.id)
  }, [user])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Nutrition & Wellness</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>

      {user?.role !== 'patient' && (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="nutrition-patient-id">Patient ID</Label>
          <Input
            id="nutrition-patient-id"
            placeholder="Enter accessible patient ID"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
          />
        </div>
      )}

      <Tabs defaultValue="nutrition" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-2 sm:h-10 sm:grid-cols-2 sm:gap-0">
          <TabsTrigger value="nutrition">Nutrition</TabsTrigger>
          <TabsTrigger value="wellness">Wellness Plan</TabsTrigger>
        </TabsList>

        <TabsContent value="nutrition" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">AI Food Scanner</CardTitle>
              <CardDescription>
                {isPatient
                  ? 'Instantly analyze your meals with AI'
                  : isDoctor
                    ? 'AI Food Analysis Tool'
                    : 'Help the patient analyze their food choices'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Upload a photo of a meal to instantly receive a clinical breakdown of ingredients, glycemic load, and healthy alternatives.
              </p>
              <NutritionAnalysisModal disabled={!isPatient && !canAssistLogging} />
            </CardContent>
          </Card>
          <MealPlannerTabContent patientId={patientId || undefined} isPatient={isPatient} />
        </TabsContent>

        <TabsContent value="wellness">
          <WellnessPlannerTabContent patientId={patientId || undefined} isPatient={isPatient} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
