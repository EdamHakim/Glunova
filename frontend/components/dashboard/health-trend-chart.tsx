'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

type TrendPoint = {
  date: string
  riskScore: number
  confidence: number
}

export default function HealthTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" stroke="var(--muted-foreground)" />
        <YAxis stroke="var(--muted-foreground)" />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
          }}
          cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="riskScore"
          stroke="var(--health-warning)"
          strokeWidth={2}
          name="Risk Score"
          dot={{ fill: 'var(--health-warning)' }}
        />
        <Line
          type="monotone"
          dataKey="confidence"
          stroke="var(--health-info)"
          strokeWidth={2}
          name="Confidence"
          dot={{ fill: 'var(--health-info)' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
