'use client'

import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

type PatientRow = {
  id: number
  name: string
  /** Uploaded profile photo URL from backend; omit or null when unavailable. */
  profilePicture?: string | null
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
  if (patients.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No entries yet. This list shows up to five assigned patients who have at least one risk assessment, newest first.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {patients.map((patient) => (
        <div
          key={patient.id}
          className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-4 flex-1">
            <Avatar className="h-10 w-10">
              <AvatarImage
                src={patient.profilePicture ?? undefined}
                alt=""
              />
              <AvatarFallback>
                {patient.name
                  .split(/\s+/)
                  .filter(Boolean)
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join('')
                  .toUpperCase() || '?'}
              </AvatarFallback>
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
