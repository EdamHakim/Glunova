'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { Activity, Apple, Camera, Check, Sparkles, UserRoundSearch } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/components/auth-context'
import { DoctorPatientPicker } from '@/components/dashboard/doctor-patient-picker'
import { NutritionAnalysisModal } from '@/components/nutrition/nutrition-analysis-modal'
import { cn } from '@/lib/utils'

const WellnessPlannerTabContent = dynamic(
  () => import('./wellness-planner/page').then((m) => ({ default: m.WellnessPlannerTabContent })),
  {
    loading: () => (
      <div className="flex min-h-[240px] items-center justify-center text-sm text-muted-foreground">
        Loading weekly planner…
      </div>
    ),
    ssr: false,
  },
)

const scannerBullets = [
  'Ingredient-level breakdown tailored to diabetes care',
  'Estimated glycemic load and calorie context',
  'Practical swaps when a meal runs high on carbs',
]

export default function NutritionPage() {
  const { user } = useAuth()
  const [patientId, setPatientId] = useState('')
  const [wellnessTabRequested, setWellnessTabRequested] = useState(false)
  const role = user?.role
  const isPatient = role === 'patient'
  const isDoctor = role === 'doctor'
  const canAssistLogging = role === 'caregiver'
  const intro = isDoctor
    ? 'Review wellness plans and food analysis for assigned patients.'
    : canAssistLogging
      ? 'Support AI food analysis and view weekly activity plans for linked patients.'
      : 'Analyze meals with AI and follow a weekly plan that balances nutrition with safe activity.'

  useEffect(() => {
    if (user?.role === 'patient') setPatientId(user.id)
  }, [user])

  return (
    <div className="relative min-h-[calc(100dvh-6rem)]">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-linear-to-b from-primary/[0.07] via-primary/2 to-transparent"
        aria-hidden
      />
      <div className="relative mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
        <header className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Lifestyle</p>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Nutrition & Activity</h1>
            <p className="text-base leading-relaxed text-muted-foreground">{intro}</p>
          </div>

          {user?.role !== 'patient' && (
            <Card className="w-full shrink-0 border-dashed bg-muted/25 lg:max-w-sm">
              <CardHeader className="space-y-1 pb-2 pt-5">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <UserRoundSearch className="h-4 w-4" />
                  <span className="text-xs font-semibold uppercase tracking-wide">Patient context</span>
                </div>
                <CardTitle className="text-base">Load data for a patient</CardTitle>
                <CardDescription>
                  {isDoctor
                    ? 'Choose an assigned patient to load nutrition and wellness data.'
                    : 'Choose a linked patient. One linked patient is selected automatically.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="pb-5">
                <DoctorPatientPicker
                  id="nutrition-patient-id"
                  label="Patient"
                  description={
                    isDoctor ? 'Patients on your care team.' : 'Patients you support as a caregiver.'
                  }
                  value={patientId}
                  onChange={setPatientId}
                  className="[&_button]:bg-background/80"
                />
              </CardContent>
            </Card>
          )}
        </header>

        <Tabs
          defaultValue="nutrition"
          className="w-full space-y-6"
          onValueChange={(value) => {
            if (value === 'wellness') setWellnessTabRequested(true)
          }}
        >
          <TabsList
            className={cn(
              'grid h-auto w-full grid-cols-2 gap-1 rounded-xl border border-border/60 bg-muted/40 p-1.5 shadow-sm',
              'sm:mx-auto sm:inline-grid sm:w-auto sm:min-w-[320px]',
            )}
          >
            <TabsTrigger
              value="nutrition"
              className="gap-2 rounded-lg py-2.5 data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Apple className="h-4 w-4 shrink-0 opacity-70" />
              Nutrition
            </TabsTrigger>
            <TabsTrigger
              value="wellness"
              className="gap-2 rounded-lg py-2.5 data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Activity className="h-4 w-4 shrink-0 opacity-70" />
              Weekly activity
            </TabsTrigger>
          </TabsList>

          <TabsContent value="nutrition" className="mt-0 space-y-0 outline-none focus-visible:outline-none">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(240px,0.85fr)] lg:items-start">
              <Card className="overflow-hidden border-border/80 shadow-md shadow-black/5">
                <CardHeader className="space-y-0 border-b bg-linear-to-br from-muted/50 to-muted/10 pb-5 pt-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/20">
                      <Camera className="h-6 w-6" />
                    </div>
                    <div className="min-w-0 space-y-1.5">
                      <CardTitle className="text-xl sm:text-2xl">AI food scanner</CardTitle>
                      <CardDescription className="text-sm leading-relaxed sm:text-base">
                        {isPatient
                          ? 'Upload a meal photo for a quick clinical-style read on ingredients, glycemic load, and safer alternatives.'
                          : isDoctor
                            ? 'Run the same AI analysis when reviewing what a patient ate.'
                            : 'Help the patient capture a meal photo and run the analysis on their behalf.'}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-5 p-5 sm:p-6">
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Works best with a clear, well-lit photo of the full plate. Results are educational and do not replace
                    medical advice from your care team.
                  </p>
                  <NutritionAnalysisModal disabled={!isPatient && !canAssistLogging} />
                </CardContent>
              </Card>

              <aside className="flex flex-col gap-4">
                <Card className="border-border/80 bg-card/80 shadow-sm backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base font-semibold">What you get</CardTitle>
                    <CardDescription>Each scan is structured for diabetes-aware coaching.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 pb-5">
                    <ul className="space-y-3">
                      {scannerBullets.map((text) => (
                        <li key={text} className="flex gap-3 text-sm leading-snug text-muted-foreground">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                            <Check className="h-3 w-3" strokeWidth={3} />
                          </span>
                          <span>{text}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
                <div className="rounded-xl border border-dashed border-primary/25 bg-primary/4 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
                  Tip: log meals on a regular schedule so your weekly activity plan and nutrition habits stay aligned.
                </div>
              </aside>
            </div>
          </TabsContent>

          <TabsContent value="wellness" className="mt-0 outline-none focus-visible:outline-none">
            <div className="rounded-2xl border border-border/80 bg-card/60 p-4 shadow-sm backdrop-blur-sm sm:p-6">
              <div className="mb-5 flex flex-col gap-2 border-b border-border/60 pb-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/12 text-primary">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold tracking-tight">Weekly activity & meals</h2>
                    <p className="text-xs text-muted-foreground sm:text-sm">
                      AI-generated sessions and meals tuned to your profile.
                    </p>
                  </div>
                </div>
              </div>
              {wellnessTabRequested ? (
                <WellnessPlannerTabContent patientId={patientId || undefined} isPatient={isPatient} />
              ) : (
                <div className="flex min-h-[200px] items-center justify-center text-center text-sm text-muted-foreground">
                  Switch to this tab to load the weekly planner.
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
