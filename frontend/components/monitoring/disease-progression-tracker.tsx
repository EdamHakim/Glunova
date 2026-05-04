'use client'

import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Bell,
  Heart,
  Layers,
  TrendingUp,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { DiseaseProgression } from '@/lib/monitoring-api'

const TIER_COLOR: Record<string, string> = {
  low: '#16a34a',       // green-600
  moderate: '#ca8a04',  // yellow-600
  high: '#ea580c',      // orange-600
  critical: '#dc2626',  // red-600
}

const TIER_LABEL: Record<string, string> = {
  low: 'LOW',
  moderate: 'MODERATE',
  high: 'HIGH',
  critical: 'CRITICAL',
}

const TREND_THEME: Record<string, { label: string; emoji: string; cls: string; chartColor: string; description: string }> = {
  worsening: {
    label: 'WORSENING',
    emoji: '↗',
    cls: 'bg-destructive text-white',
    chartColor: '#dc2626',
    description: 'Patient condition is deteriorating — immediate clinical attention recommended.',
  },
  improving: {
    label: 'IMPROVING',
    emoji: '↘',
    cls: 'bg-health-success text-white',
    chartColor: '#16a34a',
    description: 'Patient condition is improving — current management is effective.',
  },
  stable: {
    label: 'STABLE',
    emoji: '→',
    cls: 'bg-muted text-foreground',
    chartColor: 'hsl(var(--primary))',
    description: 'Patient condition is stable — continue current monitoring schedule.',
  },
  first: {
    label: 'FIRST',
    emoji: '◯',
    cls: 'bg-muted text-muted-foreground',
    chartColor: 'hsl(var(--primary))',
    description: 'First assessment recorded — at least 2 are needed to establish a trend.',
  },
}

function formatDelta(value: number | null | undefined, asPct: boolean = true): string {
  if (value === null || value === undefined) return '—'
  const sign = value > 0 ? '+' : ''
  return asPct ? `${sign}${(value * 100).toFixed(1)}%` : `${sign}${value.toFixed(2)}`
}

export function DiseaseProgressionTracker({
  data,
  loading,
  error,
}: {
  data: DiseaseProgression | null
  loading: boolean
  error: string | null
}) {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading progression…</p>
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (!data || data.assessments.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="h-5 w-5" />
            Disease Progression Tracker
          </CardTitle>
          <CardDescription>
            No risk assessments yet. Trends appear here as soon as the AI runs at least 2 fusions
            for this patient.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const trendTheme = TREND_THEME[data.trend] ?? TREND_THEME.first
  const last = data.assessments[data.assessments.length - 1]

  // Build chart data — convert score to percent so the Y axis reads in %.
  const chartData = data.assessments.map((a, idx) => ({
    label: idx === data.assessments.length - 1 ? 'Latest' : a.relative_time,
    pct: Math.round(a.score * 100),
    tier: a.tier,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="h-5 w-5 text-primary" />
          Disease Progression Tracker
        </CardTitle>
        <CardDescription>
          AI-monitored health trends over time, flagging worsening, stable, or improving conditions.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Hero: big trend flag + summary */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
          <div
            className={`flex flex-col items-center justify-center rounded-2xl p-6 shadow-md ${trendTheme.cls}`}
          >
            <span className="text-5xl drop-shadow" aria-hidden>{trendTheme.emoji}</span>
            <span className="mt-2 text-xl font-bold tracking-wide">{trendTheme.label}</span>
            <span className="mt-1 text-xs opacity-90">
              {data.n_assessments ?? 0} {(data.n_assessments ?? 0) === 1 ? 'assessment' : 'assessments'}
              {data.period_days && data.period_days > 0
                ? ` over ${data.period_days} day${data.period_days > 1 ? 's' : ''}`
                : ''}
            </span>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <p className="text-sm font-medium">{trendTheme.description}</p>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Risk score change (vs previous)</p>
                <p
                  className={`mt-0.5 text-base font-bold ${
                    (data.recent_score_delta ?? data.delta_score ?? 0) > 0.05
                      ? 'text-destructive'
                      : (data.recent_score_delta ?? data.delta_score ?? 0) < -0.05
                        ? 'text-health-success'
                        : 'text-foreground'
                  }`}
                >
                  {formatDelta(data.recent_score_delta ?? data.delta_score ?? null, true)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Tier escalations</p>
                <p className="mt-0.5 text-base font-bold">{data.tier_escalations ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Active alerts</p>
                <p className="mt-0.5 text-base font-bold">{data.active_alerts_count ?? 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Risk score timeline chart */}
        {chartData.length >= 2 ? (
          <div className="rounded-lg border bg-background p-4">
            <p className="mb-2 text-sm font-medium">Risk score timeline</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 12, right: 16, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} className="text-muted-foreground" />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${v}%`}
                    className="text-muted-foreground"
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [`${v}%`, 'Risk score']}
                  />
                  <ReferenceLine
                    y={45}
                    stroke="#ea580c"
                    strokeDasharray="4 4"
                    label={{ value: 'HIGH (45%)', position: 'right', fontSize: 10, fill: '#ea580c' }}
                  />
                  <ReferenceLine
                    y={90}
                    stroke="#dc2626"
                    strokeDasharray="4 4"
                    label={{ value: 'CRITICAL (90%)', position: 'right', fontSize: 10, fill: '#dc2626' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pct"
                    stroke={trendTheme.chartColor}
                    strokeWidth={3}
                    dot={{ r: 5, strokeWidth: 2, fill: 'white' }}
                    activeDot={{ r: 7 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : null}

        {/* Key indicators */}
        <div className="rounded-lg border bg-background p-4">
          <p className="mb-3 text-sm font-medium">Key indicators</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {data.tier_journey && data.tier_journey.length > 0 ? (
              <div className="flex items-start gap-3">
                <Layers className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">Tier journey</p>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {data.tier_journey.map((t, idx) => (
                      <span key={`${t}-${idx}`} className="flex items-center gap-1">
                        <Badge
                          variant="outline"
                          className="px-2 py-0 text-[11px]"
                          style={{ color: TIER_COLOR[t] ?? undefined, borderColor: TIER_COLOR[t] ?? undefined }}
                        >
                          {TIER_LABEL[t] ?? t.toUpperCase()}
                        </Badge>
                        {idx < (data.tier_journey?.length ?? 0) - 1 ? (
                          <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        ) : null}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            {data.confidence_evolution ? (
              <div className="flex items-start gap-3">
                <Activity className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">AI confidence</p>
                  <p className="mt-1 text-sm">
                    {(data.confidence_evolution.first * 100).toFixed(0)}% →{' '}
                    <span className="font-semibold">
                      {(data.confidence_evolution.last * 100).toFixed(0)}%
                    </span>{' '}
                    <span
                      className={`text-xs ${
                        data.confidence_evolution.delta > 0
                          ? 'text-health-success'
                          : data.confidence_evolution.delta < 0
                            ? 'text-destructive'
                            : 'text-muted-foreground'
                      }`}
                    >
                      ({formatDelta(data.confidence_evolution.delta, true)})
                    </span>
                  </p>
                </div>
              </div>
            ) : null}

            {data.modalities_evolution ? (
              <div className="flex items-start gap-3">
                <Heart className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">Signals contributing</p>
                  <p className="mt-1 text-sm">
                    {data.modalities_evolution.first} → <span className="font-semibold">{data.modalities_evolution.last}</span>{' '}
                    {data.modalities_evolution.last === 1 ? 'modality' : 'modalities'}
                  </p>
                </div>
              </div>
            ) : null}

            {data.active_alerts_count !== undefined ? (
              <div className="flex items-start gap-3">
                <Bell className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">Active alerts</p>
                  <p className="mt-1 text-sm font-semibold">{data.active_alerts_count}</p>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* Latest assessment summary */}
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          <p className="text-xs text-muted-foreground">Latest assessment</p>
          <p className="mt-1">
            <Badge
              variant="outline"
              className="mr-2"
              style={{ color: TIER_COLOR[last.tier] ?? undefined, borderColor: TIER_COLOR[last.tier] ?? undefined }}
            >
              {TIER_LABEL[last.tier] ?? last.tier.toUpperCase()}
            </Badge>
            Score {(last.score * 100).toFixed(1)}% · Confidence {(last.confidence * 100).toFixed(0)}% ·{' '}
            {last.n_models_used} {last.n_models_used === 1 ? 'signal' : 'signals'} · {last.relative_time}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
