'use client'

import { useEffect, useMemo, useState } from 'react'
import { MessageSquare, Activity } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { listExercisePlans, type ExercisePlanRow } from '@/lib/nutrition-api'
import { NutritionAnalysisModal } from '@/components/nutrition/nutrition-analysis-modal'
import { MealPlannerTabContent } from './meal-planner/page'

export default function NutritionPage() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [exercisePlans, setExercisePlans] = useState<ExercisePlanRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const role = user?.role
  const isPatient = role === 'patient'
  const isDoctor = role === 'doctor'
  const canAssistLogging = role === 'caregiver'
  const intro = isDoctor
    ? 'Review activity guidance for assigned patients.'
    : canAssistLogging
      ? 'Support AI food analysis and follow the shared exercise plan for linked patients.'
      : 'Analyze meals with AI and track exercise recommendations.'

  useEffect(() => {
    if (user?.role === 'patient') setPatientId(user.id)
  }, [user])

  const loadData = (pid: string) => {
    setLoading(true)
    setError(null)
    listExercisePlans(pid)
      .then((exercisePayload) => {
        setExercisePlans(exercisePayload.items)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load nutrition data')
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    if (!patientId) {
      setExercisePlans([])
      return
    }
    loadData(patientId)
  }, [patientId])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Nutrition & Physical Activity</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>
      {user?.role !== 'patient' && (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="nutrition-patient-id">Patient ID</Label>
          <Input
            id="nutrition-patient-id"
            placeholder="Enter accessible patient ID"
            value={patientId}
            onChange={(event) => setPatientId(event.target.value)}
          />
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Tabs defaultValue="nutrition" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-2 sm:h-10 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="nutrition">Nutrition</TabsTrigger>
          <TabsTrigger value="exercise">Exercise</TabsTrigger>
          <TabsTrigger value="ai-coach">AI Coach</TabsTrigger>
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

        <TabsContent value="exercise" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Exercise Recommendations</CardTitle>
              <CardDescription>
                {isDoctor ? 'Review and reinforce the patient activity plan' : 'Personalized activity plan based on health profile'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {loading && <p className="text-sm text-muted-foreground">Loading exercise plan...</p>}
                {!loading && exercisePlans.length === 0 && (
                  <p className="text-sm text-muted-foreground">No exercise plans available for this patient scope.</p>
                )}
                {exercisePlans.map((plan) => (
                  <div key={plan.id} className="p-4 border border-border rounded-lg">
                    <Activity className="h-6 w-6 text-health-success mb-2" />
                    <p className="font-medium">{plan.title}</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {plan.duration_minutes} mins • {plan.intensity}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {new Date(plan.scheduled_for).toLocaleString()} • {plan.status}
                    </p>
                    {plan.recovery_plan?.next_session_tip && (
                      <p className="text-xs text-health-info mt-2">{plan.recovery_plan.next_session_tip}</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai-coach" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Nutrition Coach</CardTitle>
              <CardDescription>
                {isPatient
                  ? 'Chat with your personal AI health assistant'
                  : 'Conversational coaching is reserved for patient accounts while cross-user scope is being tightened.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isPatient ? (
                <div className="h-96 border border-border rounded-lg bg-muted/30 p-4 flex flex-col">
                  <div className="flex-1 space-y-4 overflow-y-auto mb-4">
                    <div className="flex justify-start">
                      <div className="bg-primary/10 text-primary px-4 py-2 rounded-lg max-w-xs">
                        <p className="text-sm">Hello! I&apos;m your nutrition coach. How can I help you today?</p>
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <div className="bg-primary text-primary-foreground px-4 py-2 rounded-lg max-w-xs">
                        <p className="text-sm">What should I eat for dinner?</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ask me anything about nutrition..."
                      className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-sm"
                    />
                    <Button size="icon">
                      <MessageSquare className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="font-medium">{isDoctor ? 'Doctor view' : 'Caregiver view'}</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    You can review plans and encourage adherence here, but interactive AI nutrition coaching remains patient-only for now.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
