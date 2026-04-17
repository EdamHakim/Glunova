'use client'

import { MessageSquare, FileText, Bell, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { MedicalDocumentsSection } from '@/components/care-circle/medical-documents-section'
import { useAuth } from '@/components/auth-context'

const familyMembers = [
  {
    name: 'Mary Anderson',
    role: 'Spouse',
    status: 'Active',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Mary',
  },
  {
    name: 'James Anderson Jr.',
    role: 'Son',
    status: 'Active',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=James',
  },
  {
    name: 'Dr. Patricia Smith',
    role: 'Primary Care Physician',
    status: 'Available',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Patricia',
  },
]

const updates = [
  {
    id: 1,
    from: 'Mary Anderson',
    message: 'How are you feeling today? Let me know if you need anything.',
    time: '2 hours ago',
  },
  {
    id: 2,
    from: 'System',
    message: 'Care plan updated: Added new exercise routine',
    time: '1 day ago',
  },
  {
    id: 3,
    from: 'Dr. Patricia Smith',
    message: 'Great progress! Keep up with the monitoring.',
    time: '2 days ago',
  },
]

export default function CareCirclePage() {
  const { user } = useAuth()
  const role = user?.role
  const canClinicallyEdit = role === 'doctor'
  const intro =
    role === 'doctor'
      ? 'Coordinate with caregivers and keep shared care plans aligned for assigned patients.'
      : role === 'caregiver'
        ? 'Stay informed, help with routines, and support the linked patient day to day.'
        : 'Connect with family, caregivers, and healthcare providers.'

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Care Circle</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Care Team
          </CardTitle>
          <CardDescription>Family members and healthcare providers</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {familyMembers.map((member, idx) => (
            <div
              key={idx}
              className="flex flex-col gap-3 border border-border p-4 rounded-lg transition-colors hover:bg-muted/50 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-center gap-4">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={member.avatar} />
                  <AvatarFallback>{member.name.split(' ').map((n) => n[0]).join('')}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{member.name}</p>
                  <p className="text-xs text-muted-foreground">{member.role}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 self-end sm:self-auto">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  {member.status}
                </Badge>
                <Button size="icon" variant="ghost">
                  <MessageSquare className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <MedicalDocumentsSection />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Shared Care Plan
            </CardTitle>
            <CardDescription>
              {canClinicallyEdit
                ? 'Shared plan you can refine with medical guidance'
                : 'Current health plan shared with the care circle'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Daily Routine</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Morning: Check blood pressure and glucose levels</li>
                <li>Midday: Walk for 30 minutes</li>
                <li>Evening: Log meals and complete stretching</li>
              </ul>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Medications</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Metformin 500mg • Twice daily</li>
                <li>Lisinopril 10mg • Once daily</li>
              </ul>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <h4 className="font-medium mb-2">Goals</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Reduce HbA1c by 0.5% in 3 months</li>
                <li>Achieve stable blood pressure readings</li>
                <li>Increase exercise frequency to 5x per week</li>
              </ul>
            </div>
            <div className="rounded-lg border border-dashed border-border p-4">
              <p className="font-medium">{canClinicallyEdit ? 'Doctor note' : 'Participation note'}</p>
              <p className="text-sm text-muted-foreground mt-2">
                {canClinicallyEdit
                  ? 'You can update this plan clinically, but document and monitoring access remain relationship-scoped.'
                  : 'You can follow this plan and coordinate around it, but medically authoritative edits remain clinician-led.'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Updates & Messages
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {updates.map((update) => (
              <div key={update.id} className="p-3 border border-border rounded-lg hover:bg-muted/50 transition-colors">
                <p className="font-medium text-sm">{update.from}</p>
                <p className="text-sm text-muted-foreground mt-1">{update.message}</p>
                <p className="text-xs text-muted-foreground mt-2">{update.time}</p>
              </div>
            ))}
            <Button variant="outline" className="w-full">
              View All
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Family Support Chat
          </CardTitle>
          <CardDescription>
            {role === 'doctor'
              ? 'Coordinate next steps with the support network'
              : 'Connect with caregivers and family'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="h-48 border border-border rounded-lg bg-muted/30 p-4 overflow-y-auto">
              <div className="space-y-3">
                <div className="flex justify-start">
                  <div className="bg-primary/10 text-primary px-3 py-2 rounded-lg max-w-xs">
                    <p className="text-sm font-medium">Mary</p>
                    <p className="text-sm">How did your screening go today?</p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="bg-primary text-primary-foreground px-3 py-2 rounded-lg max-w-xs">
                    <p className="text-sm">Pretty good! Risk score is down to 45.</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder={
                  role === 'doctor'
                    ? 'Share a care-plan update with the support team...'
                    : 'Message your care team...'
                }
                className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-sm"
              />
              <Button size="icon">
                <MessageSquare className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
