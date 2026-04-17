'use client'

import { AlertCircle, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/components/auth-context'

const alerts = [
  {
    id: 1,
    severity: 'Critical',
    title: 'High Blood Pressure',
    description: 'Patient John Anderson - Systolic 180 mmHg',
    time: '2 hours ago',
  },
  {
    id: 2,
    severity: 'High',
    title: 'Glucose Out of Range',
    description: 'Patient Emily Chen - Fasting glucose 280 mg/dL',
    time: '5 hours ago',
  },
  {
    id: 3,
    severity: 'Moderate',
    title: 'Irregular Heart Rate',
    description: 'Patient Michael Davis - HR variability detected',
    time: '1 day ago',
  },
]

const timelineEvents = [
  {
    date: 'Today',
    time: '02:30 PM',
    patient: 'John Anderson',
    event: 'Blood Pressure Spike',
    value: '180/110 mmHg',
  },
  {
    date: 'Today',
    time: '10:15 AM',
    patient: 'Emily Chen',
    event: 'Screening Completed',
    value: 'Risk Score: 52',
  },
  {
    date: 'Yesterday',
    time: '04:45 PM',
    patient: 'Sarah Wilson',
    event: 'Meal Logged',
    value: '2000 cal, Balanced',
  },
  {
    date: 'Yesterday',
    time: '02:00 PM',
    patient: 'Michael Davis',
    event: 'Psychology Session',
    value: 'Completed - Stable',
  },
]

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'Critical':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    case 'High':
      return 'bg-health-danger/10 text-health-danger border-health-danger/20'
    case 'Moderate':
      return 'bg-health-warning/10 text-health-warning border-health-warning/20'
    default:
      return 'bg-health-success/10 text-health-success border-health-success/20'
  }
}

export default function MonitoringPage() {
  const { user } = useAuth()
  const role = user?.role
  const isCaregiver = role === 'caregiver'
  const isDoctor = role === 'doctor'
  const intro = isDoctor
    ? 'Track assigned patient alerts, trends, and escalation signals.'
    : isCaregiver
      ? 'Follow linked patient updates, reminders, and high-level alerts.'
      : 'Track your health alerts, timeline, and progression over time.'

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Monitoring & Analytics</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>

      <Tabs defaultValue="alerts" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-2 sm:h-10 sm:grid-cols-3 sm:gap-0">
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="progression">Progression</TabsTrigger>
        </TabsList>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active Alerts</CardTitle>
              <CardDescription>
                {isDoctor
                  ? 'Assigned patients requiring immediate attention'
                  : isCaregiver
                    ? 'Important updates you may need to help with'
                    : 'Your latest health alerts and reminders'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {alerts.map((alert) => (
                <div key={alert.id} className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div className="flex gap-4 flex-1">
                      <AlertCircle
                        className={`h-5 w-5 mt-0.5 shrink-0 ${
                          alert.severity === 'Critical'
                            ? 'text-destructive'
                            : alert.severity === 'High'
                              ? 'text-health-danger'
                              : 'text-health-warning'
                        }`}
                      />
                      <div>
                        <p className="font-medium">{alert.title}</p>
                        <p className="text-sm text-muted-foreground mt-1">{alert.description}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                      <Badge className={getSeverityColor(alert.severity)}>{alert.severity}</Badge>
                      <span className="text-xs text-muted-foreground">{alert.time}</span>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Patient Event Timeline</CardTitle>
              <CardDescription>
                {isCaregiver ? 'Recent shareable events and care activities' : 'Recent health events and assessments'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {timelineEvents.map((event, idx) => (
                  <div key={idx} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                        <Clock className="h-5 w-5 text-primary" />
                      </div>
                      {idx < timelineEvents.length - 1 && <div className="w-0.5 h-12 bg-border mt-2" />}
                    </div>
                    <div className="pb-4">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{event.event}</p>
                        <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">{event.value}</span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">{event.patient}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {event.date} at {event.time}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="progression" className="space-y-4">
          {isCaregiver ? (
            <Card>
              <CardHeader>
                <CardTitle>Progression Summary</CardTitle>
                <CardDescription>Caregiver access is limited to high-level trend visibility.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="font-medium">Clinician-level trends are hidden</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    You can continue following alerts, reminders, and care-plan updates here without seeing the full clinical progression view.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Disease Progression Charts</CardTitle>
                <CardDescription>
                  {isDoctor ? 'Long-term trends across assigned patient risk categories' : 'Long-term health trends by patient risk category'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium">Low Risk Patients</span>
                    <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                      12 patients
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Avg Risk Score</span>
                      <span className="font-medium">28</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div className="bg-health-success h-2 rounded-full" style={{ width: '28%' }} />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium">Moderate Risk Patients</span>
                    <Badge variant="outline" className="bg-health-warning/10 text-health-warning border-health-warning/20">
                      8 patients
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Avg Risk Score</span>
                      <span className="font-medium">52</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div className="bg-health-warning h-2 rounded-full" style={{ width: '52%' }} />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium">High Risk Patients</span>
                    <Badge variant="outline" className="bg-health-danger/10 text-health-danger border-health-danger/20">
                      3 patients
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Avg Risk Score</span>
                      <span className="font-medium">78</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div className="bg-health-danger h-2 rounded-full" style={{ width: '78%' }} />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
