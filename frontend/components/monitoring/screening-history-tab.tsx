'use client'

import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Eye,
  Footprints,
  type LucideIcon,
  ScanSearch,
  Stethoscope,
  Thermometer,
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
import type { ScreeningModalitySummary, ScreeningScan } from '@/lib/monitoring-api'

const MODALITY_ICONS: Record<string, LucideIcon> = {
  retinopathy: Eye,
  cataract: Eye,
  infrared: Thermometer,
  foot_ulcer: Footprints,
  tongue: ScanSearch,
  voice: Stethoscope,
}

// Per-modality clinical reference (threshold above which the signal is clinically concerning).
const REFERENCE_THRESHOLDS: Record<string, { value: number; label: string }> = {
  retinopathy: { value: 0.5, label: 'DR detection' },
  infrared: { value: 0.3, label: 'Asymmetric filter' },
  foot_ulcer: { value: 0.3, label: 'Asymmetric filter' },
  cataract: { value: 0.3, label: 'Asymmetric filter' },
  tongue: { value: 0.5, label: 'Diabetes signal' },
}

function severityColor(score: number): string {
  if (score >= 0.75) return '#dc2626'  // red-600
  if (score >= 0.5) return '#ea580c'   // orange-600
  if (score >= 0.25) return '#ca8a04'  // yellow-600
  return '#16a34a'                      // green-600
}

function trendVisual(trend: ScreeningModalitySummary['trend'], delta: number | null) {
  if (trend === 'first') {
    return {
      icon: ArrowRight,
      cls: 'bg-muted text-muted-foreground border-border',
      text: 'First scan',
    }
  }
  const Icon = trend === 'worsening' ? ArrowUp : trend === 'improving' ? ArrowDown : ArrowRight
  const cls =
    trend === 'worsening'
      ? 'bg-destructive/10 text-destructive border-destructive/20'
      : trend === 'improving'
        ? 'bg-health-success/10 text-health-success border-health-success/20'
        : 'bg-muted text-muted-foreground border-border'
  const deltaText = delta !== null ? ` ${delta > 0 ? '+' : ''}${(delta * 100).toFixed(0)}%` : ''
  return { icon: Icon, cls, text: `${trend.charAt(0).toUpperCase() + trend.slice(1)}${deltaText}` }
}

function chartDataFor(scans: ScreeningScan[]): { label: string; score: number; pct: number }[] {
  // Reverse newest→oldest into oldest→newest so the chart reads left-to-right in time.
  return [...scans].reverse().map((s, idx, arr) => ({
    label: idx === arr.length - 1 ? 'Now' : s.relative_time,
    score: s.score,
    pct: Math.round(s.score * 100),
  }))
}

function ModalityCard({ m }: { m: ScreeningModalitySummary }) {
  const Icon = MODALITY_ICONS[m.modality] ?? Activity
  const trend = trendVisual(m.trend, m.delta_score)
  const TrendIcon = trend.icon
  const ref = REFERENCE_THRESHOLDS[m.modality]
  const data = chartDataFor(m.scans)
  const latestColor = severityColor(m.latest.score)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
              <Icon className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{m.label}</CardTitle>
              <CardDescription>
                {m.scan_count} {m.scan_count === 1 ? 'scan' : 'scans'} on record
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className={`${trend.cls} flex items-center gap-1.5 px-3 py-1`}>
            <TrendIcon className="h-3.5 w-3.5" />
            {trend.text}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Hero row: 3 KPIs */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border bg-background p-3">
            <p className="text-xs text-muted-foreground">Latest score</p>
            <p className="mt-1 text-2xl font-bold" style={{ color: latestColor }}>
              {(m.latest.score * 100).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-lg border bg-background p-3">
            <p className="text-xs text-muted-foreground">Diagnosis</p>
            <p className="mt-1 truncate text-base font-semibold" title={m.latest.risk_label}>
              {m.latest.risk_label}
            </p>
          </div>
          <div className="rounded-lg border bg-background p-3">
            <p className="text-xs text-muted-foreground">Last scan</p>
            <p className="mt-1 text-base font-semibold">{m.latest.relative_time}</p>
          </div>
        </div>

        {/* Chart */}
        {data.length >= 2 ? (
          <div className="rounded-lg border bg-background p-4">
            <p className="mb-2 text-sm font-medium">Score evolution</p>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 12, right: 16, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    className="text-muted-foreground"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${v}%`}
                    className="text-muted-foreground"
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [`${v}%`, 'Score']}
                  />
                  {ref ? (
                    <ReferenceLine
                      y={ref.value * 100}
                      stroke="#ea580c"
                      strokeDasharray="4 4"
                      label={{
                        value: `${ref.label} (${(ref.value * 100).toFixed(0)}%)`,
                        position: 'right',
                        fontSize: 10,
                        fill: '#ea580c',
                      }}
                    />
                  ) : null}
                  <Line
                    type="monotone"
                    dataKey="pct"
                    stroke="hsl(var(--primary))"
                    strokeWidth={3}
                    dot={{ r: 5, strokeWidth: 2, fill: 'white' }}
                    activeDot={{ r: 7 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-center">
            <p className="text-sm text-muted-foreground">
              Only one scan recorded — at least 2 are needed to plot a trend.
            </p>
          </div>
        )}

        {/* Recent scans list */}
        <div>
          <p className="mb-2 text-sm font-medium">Recent scans</p>
          <div className="space-y-1.5">
            {m.scans.map((s, idx) => {
              const color = severityColor(s.score)
              return (
                <div
                  key={`${m.modality}-${idx}`}
                  className={`flex items-center gap-3 rounded-md border px-3 py-2 text-sm ${idx === 0 ? 'border-primary/40 bg-primary/5' : 'border-border'}`}
                >
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: color }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{s.risk_label}</p>
                    <p className="text-xs text-muted-foreground">{s.relative_time}</p>
                  </div>
                  <span className="ml-3 shrink-0 font-mono text-sm font-semibold" style={{ color }}>
                    {(s.score * 100).toFixed(0)}%
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function ScreeningHistoryTab({
  modalities,
  loading,
  error,
}: {
  modalities: ScreeningModalitySummary[]
  loading: boolean
  error: string | null
}) {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading screening history…</p>
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (modalities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-5 w-5" />
            No screening history yet
          </CardTitle>
          <CardDescription>
            Each scan (DR, Thermal foot, Tongue, DFU…) the doctor runs will be stored here, grouped
            by modality, with longitudinal trend tracking.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {modalities.map((m) => (
        <ModalityCard key={m.modality} m={m} />
      ))}
    </div>
  )
}
