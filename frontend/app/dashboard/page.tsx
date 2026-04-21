'use client'

import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import HealthTrendChart from '@/components/dashboard/health-trend-chart'
import PatientSummary from '@/components/dashboard/patient-summary'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'
import { getDashboardOverview, type DashboardOverview } from '@/lib/dashboard-api'

export default function Dashboard() {
  const { user, loading } = useAuth()
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (loading) return
    if (user?.role !== 'doctor') {
      setOverview(null)
      setError(null)
      return
    }
    let cancelled = false
    void getDashboardOverview()
      .then((payload) => {
        if (!cancelled) setOverview(payload)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load dashboard')
      })
    return () => {
      cancelled = true
    }
  }, [loading, user?.role])

  const trendData = useMemo(
    () =>
      (overview?.trend ?? []).map((point) => ({
        date: point.date,
        riskScore: Math.round(point.risk_score * 100),
        confidence: Math.round(point.confidence * 100),
      })),
    [overview],
  )

  const recentPatients = useMemo(
    () =>
      (overview?.recent_patients ?? []).map((patient) => ({
        id: patient.id,
        name: patient.name,
        riskLevel: patient.risk_level,
        lastScreening: new Date(patient.last_assessment).toLocaleString(),
        status: patient.status,
      })),
    [overview],
  )

  return (
    <RoleGuard
      allowedRoles={['doctor']}
      title="Dashboard unavailable"
      description="The overview dashboard is accessible only to doctor accounts."
    >
      <div className="space-y-6 p-4 sm:p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Dashboard</h1>
        <p className="text-muted-foreground mt-2">Overview of your assigned patient cohort.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Patients</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview?.stats.active_patients ?? 0}</div>
            <p className="text-xs text-health-success flex items-center gap-1 mt-1">
              <TrendingUp className="h-3 w-3" /> Assigned to your care plans
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending Screenings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-health-warning">{overview?.stats.pending_screenings ?? 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Due within 7 days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-health-danger">{overview?.stats.alerts ?? 0}</div>
            <p className="text-xs text-health-danger flex items-center gap-1 mt-1">
              <AlertCircle className="h-3 w-3" /> Requires attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Risk Score (Avg)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Math.round(overview?.stats.avg_risk_score ?? 0)}</div>
            <p className="text-xs text-muted-foreground mt-1">Moderate risk</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Health Progression</CardTitle>
            <CardDescription>Patient risk scores over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <HealthTrendChart data={trendData} />
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button className="w-full justify-start" variant="outline">
              New Screening
            </Button>
            <Button className="w-full justify-start" variant="outline">
              View Alerts
            </Button>
            <Button className="w-full justify-start" variant="outline">
              Log Meal
            </Button>
            <Button className="w-full justify-start" variant="outline">
              Psychology Session
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Patient Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Patients</CardTitle>
          <CardDescription>Latest patient assessments and status</CardDescription>
        </CardHeader>
        <CardContent>
          <PatientSummary patients={recentPatients} />
        </CardContent>
      </Card>
      </div>
    </RoleGuard>
  )
}
