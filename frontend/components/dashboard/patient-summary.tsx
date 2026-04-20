'use client'

import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

type PatientRow = {
  id: number
  name: string
  riskLevel: 'Low' | 'Moderate' | 'High' | 'Critical'
  lastScreening: string
  status: string
}

function getRiskBadgeColor(riskLevel: string) {
  switch (riskLevel) {
    case 'Low':
      return 'bg-health-success/10 text-health-success border-health-success/20'
    case 'Moderate':
      return 'bg-health-warning/10 text-health-warning border-health-warning/20'
    case 'High':
      return 'bg-health-danger/10 text-health-danger border-health-danger/20'
    case 'Critical':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

export default function PatientSummary({ patients }: { patients: PatientRow[] }) {
  return (
    <div className="space-y-3">
      {patients.map((patient) => (
        <div
          key={patient.id}
          className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-4 flex-1">
            <Avatar className="h-10 w-10">
              <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(patient.name)}`} />
              <AvatarFallback>{patient.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="font-medium text-sm">{patient.name}</p>
              <p className="text-xs text-muted-foreground">Last: {patient.lastScreening}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className={getRiskBadgeColor(patient.riskLevel)}>
              {patient.riskLevel}
            </Badge>
            <span className="text-xs font-medium text-muted-foreground w-24 text-right">
              {patient.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
