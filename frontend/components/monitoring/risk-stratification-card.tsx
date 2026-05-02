'use client'

import { ArrowDown, ArrowRight, ArrowUp, Lightbulb, Target } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { RiskStratification } from '@/lib/monitoring-api'

const TIER_THEME: Record<string, { label: string; emoji: string; cardBg: string; tierBg: string; tierText: string; pulse: boolean }> = {
  low: {
    label: 'LOW',
    emoji: '🟢',
    cardBg: 'bg-health-success/5 border-health-success/30',
    tierBg: 'bg-linear-to-br from-health-success to-health-success/70',
    tierText: 'text-white',
    pulse: false,
  },
  moderate: {
    label: 'MODERATE',
    emoji: '🟡',
    cardBg: 'bg-health-warning/5 border-health-warning/30',
    tierBg: 'bg-linear-to-br from-health-warning to-health-warning/70',
    tierText: 'text-white',
    pulse: false,
  },
  high: {
    label: 'HIGH',
    emoji: '🟠',
    cardBg: 'bg-health-danger/5 border-health-danger/30',
    tierBg: 'bg-linear-to-br from-health-danger to-health-danger/70',
    tierText: 'text-white',
    pulse: false,
  },
  critical: {
    label: 'CRITICAL',
    emoji: '🔴',
    cardBg: 'bg-destructive/5 border-destructive/40',
    tierBg: 'bg-linear-to-br from-destructive to-destructive/70',
    tierText: 'text-white',
    pulse: true,
  },
}

function trendBadge(trend: RiskStratification['trend'], delta: number | null) {
  const Icon = trend === 'worsening' ? ArrowUp : trend === 'improving' ? ArrowDown : ArrowRight
  const cls =
    trend === 'worsening'
      ? 'bg-destructive/10 text-destructive border-destructive/20'
      : trend === 'improving'
        ? 'bg-health-success/10 text-health-success border-health-success/20'
        : 'bg-muted text-muted-foreground border-border'
  const text =
    trend === 'first'
      ? 'First assessment'
      : `${trend.charAt(0).toUpperCase() + trend.slice(1)}${delta !== null ? ` (${delta > 0 ? '+' : ''}${(delta * 100).toFixed(1)}%)` : ''}`
  return (
    <Badge variant="outline" className={`${cls} flex items-center gap-1`}>
      <Icon className="h-3.5 w-3.5" />
      {text}
    </Badge>
  )
}

export function RiskStratificationCard({
  data,
  loading,
  error,
}: {
  data: RiskStratification | null
  loading: boolean
  error: string | null
}) {
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            Current Risk Assessment
          </CardTitle>
          <CardDescription>Loading…</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            Current Risk Assessment
          </CardTitle>
          <CardDescription className="text-destructive">{error}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (!data || !data.current) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            Current Risk Assessment
          </CardTitle>
          <CardDescription>
            No risk assessment yet. The AI will compute one once the patient signs up or has their
            first scan.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const cur = data.current
  const theme = TIER_THEME[cur.tier] ?? TIER_THEME.low
  const probabilityPct = (cur.score * 100).toFixed(1)
  const confidencePct = (cur.confidence * 100).toFixed(0)

  return (
    <Card className={`border-2 ${theme.cardBg}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          Current Risk Assessment
        </CardTitle>
        <CardDescription>AI-fused diabetes risk based on all available signals.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-stretch">
          {/* Big tier badge */}
          <div
            className={`relative flex h-40 w-40 shrink-0 flex-col items-center justify-center rounded-2xl shadow-lg ${theme.tierBg} ${theme.tierText} ${theme.pulse ? 'animate-pulse' : ''}`}
          >
            <span className="text-5xl drop-shadow" aria-hidden>{theme.emoji}</span>
            <span className="mt-2 text-xl font-bold tracking-wide">{theme.label}</span>
          </div>

          {/* Metrics */}
          <div className="flex flex-1 flex-col justify-center gap-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg border bg-background/60 p-3">
                <p className="text-xs text-muted-foreground">Diabetes probability</p>
                <p className="mt-1 text-2xl font-bold">{probabilityPct}%</p>
              </div>
              <div className="rounded-lg border bg-background/60 p-3">
                <p className="text-xs text-muted-foreground">AI confidence</p>
                <p className="mt-1 text-2xl font-bold">{confidencePct}%</p>
                <p className="text-[10px] text-muted-foreground">
                  Based on {cur.n_models_used} {cur.n_models_used === 1 ? 'signal' : 'signals'}
                </p>
              </div>
              <div className="rounded-lg border bg-background/60 p-3">
                <p className="text-xs text-muted-foreground mb-1">Trend vs last</p>
                {trendBadge(data.trend, data.delta_score)}
              </div>
              <div className="rounded-lg border bg-background/60 p-3">
                <p className="text-xs text-muted-foreground">Last updated</p>
                <p className="mt-1 text-sm font-medium">{cur.relative_time}</p>
              </div>
            </div>

            <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
              <p className="flex items-center gap-2 text-xs font-semibold text-primary">
                <Lightbulb className="h-4 w-4" />
                Recommendation
              </p>
              <p className="mt-1 text-sm">{cur.recommendation}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
