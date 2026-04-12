'use client'

import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

const patients = [
  {
    id: 1,
    name: 'John Anderson',
    age: 68,
    riskLevel: 'High',
    lastScreening: '2 days ago',
    status: 'Requires Follow-up',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=John',
  },
  {
    id: 2,
    name: 'Emily Chen',
    age: 45,
    riskLevel: 'Moderate',
    lastScreening: '5 days ago',
    status: 'Monitoring',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Emily',
  },
  {
    id: 3,
    name: 'Michael Davis',
    age: 72,
    riskLevel: 'Critical',
    lastScreening: 'Today',
    status: 'Alert',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Michael',
  },
  {
    id: 4,
    name: 'Sarah Wilson',
    age: 52,
    riskLevel: 'Low',
    lastScreening: '1 week ago',
    status: 'Stable',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah',
  },
  {
    id: 5,
    name: 'James Martinez',
    age: 65,
    riskLevel: 'Moderate',
    lastScreening: '3 days ago',
    status: 'Monitoring',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=James',
  },
]

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

export default function PatientSummary() {
  return (
    <div className="space-y-3">
      {patients.map((patient) => (
        <div
          key={patient.id}
          className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-4 flex-1">
            <Avatar className="h-10 w-10">
              <AvatarImage src={patient.avatar} />
              <AvatarFallback>{patient.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="font-medium text-sm">{patient.name}</p>
              <p className="text-xs text-muted-foreground">Age: {patient.age} • Last: {patient.lastScreening}</p>
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
