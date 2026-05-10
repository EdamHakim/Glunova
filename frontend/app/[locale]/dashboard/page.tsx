'use client'

import dynamic from 'next/dynamic'
import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, TrendingUp } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import PatientSummary from '@/components/dashboard/patient-summary'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'
import { getDashboardOverview, type DashboardOverview } from '@/lib/dashboard-api'

const HealthTrendChart = dynamic(() => import('@/components/dashboard/health-trend-chart'), {
  loading: () => (
    <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
      {/* loaded inside client component — fine */}
    </div>
  ),
  ssr: false,
})

export default function Dashboard() {
  const { user, loading } = useAuth()
  const t = useTranslations('dashboard')
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (loading) return
    if (user?.role !== 'doctor') { setOverview(null); setError(null); return }
    let cancelled = false
    void getDashboardOverview()
      .then((payload) => { if (!cancelled) setOverview(payload) })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : t('failedToLoad')) })
    return () => { cancelled = true }
  }, [loading, user?.role, t])

  const trendData = useMemo(
    () => (overview?.trend ?? []).map((p) => ({ date: p.date, riskScore: Math.round(p.risk_score * 100), confidence: Math.round(p.confidence * 100) })),
    [overview],
  )

  const recentPatients = useMemo(
    () => (overview?.recent_patients ?? []).map((p) => ({
      id: p.id, name: p.name, profilePicture: p.profile_picture,
      riskLevel: p.risk_level, lastScreening: new Date(p.last_assessment).toLocaleString(), status: p.status,
    })),
    [overview],
  )

  return (
    <RoleGuard allowedRoles={['doctor']} title={t('unavailableTitle')} description={t('unavailableDesc')}>
      <div className="space-y-6 p-4 sm:p-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
          <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('activePatients')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{overview?.stats.active_patients ?? 0}</div>
              <p className="text-xs text-health-success flex items-center gap-1 mt-1">
                <TrendingUp className="h-3 w-3" /> {t('assignedCarePlans')}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('pendingScreenings')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-health-warning">{overview?.stats.pending_screenings ?? 0}</div>
              <p className="text-xs text-muted-foreground mt-1">{t('dueWithin7Days')}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('alerts')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-health-danger">{overview?.stats.alerts ?? 0}</div>
              <p className="text-xs text-health-danger flex items-center gap-1 mt-1">
                <AlertCircle className="h-3 w-3" /> {t('requiresAttention')}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t('riskScoreAvg')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{Math.round(overview?.stats.avg_risk_score ?? 0)}</div>
              <p className="text-xs text-muted-foreground mt-1">{t('moderateRisk')}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{t('healthProgression')}</CardTitle>
              <CardDescription>{t('riskScoresLast30')}</CardDescription>
            </CardHeader>
            <CardContent>
              <HealthTrendChart data={trendData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t('quickActions')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button asChild className="w-full justify-start" variant="outline">
                <Link href="/dashboard/monitoring">{t('viewPatientMonitoring')}</Link>
              </Button>
              <Button asChild className="w-full justify-start" variant="outline">
                <Link href="/dashboard/clinical">{t('clinicalSupport')}</Link>
              </Button>
              <Button asChild className="w-full justify-start" variant="outline">
                <Link href="/dashboard/schedule">{t('manageAvailability')}</Link>
              </Button>
              <Button asChild className="w-full justify-start" variant="outline">
                <Link href="/dashboard/care-circle">{t('careCircle')}</Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t('recentPatients')}</CardTitle>
            <CardDescription>{t('latestAssessments')}</CardDescription>
          </CardHeader>
          <CardContent>
            <PatientSummary patients={recentPatients} />
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}
