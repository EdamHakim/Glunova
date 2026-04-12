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

const data = [
  { date: 'Day 1', riskScore: 65, bloodPressure: 140, glucose: 180 },
  { date: 'Day 5', riskScore: 62, bloodPressure: 138, glucose: 175 },
  { date: 'Day 10', riskScore: 58, bloodPressure: 135, glucose: 170 },
  { date: 'Day 15', riskScore: 55, bloodPressure: 132, glucose: 165 },
  { date: 'Day 20', riskScore: 52, bloodPressure: 130, glucose: 160 },
  { date: 'Day 25', riskScore: 50, bloodPressure: 128, glucose: 155 },
  { date: 'Day 30', riskScore: 48, bloodPressure: 125, glucose: 150 },
]

export default function HealthTrendChart() {
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
          dataKey="bloodPressure"
          stroke="var(--health-danger)"
          strokeWidth={2}
          name="Blood Pressure (Systolic)"
          dot={{ fill: 'var(--health-danger)' }}
        />
        <Line
          type="monotone"
          dataKey="glucose"
          stroke="var(--health-info)"
          strokeWidth={2}
          name="Glucose Level"
          dot={{ fill: 'var(--health-info)' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
