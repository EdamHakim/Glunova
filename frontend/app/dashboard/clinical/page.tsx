import { Stethoscope, AlertTriangle, Image as ImageIcon, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

const prioritizedPatients = [
  {
    rank: 1,
    name: 'John Anderson',
    risk: 'Critical',
    issue: 'High BP spike detected',
    lastUpdate: '2 hours ago',
    urgency: 'High',
  },
  {
    rank: 2,
    name: 'Michael Davis',
    risk: 'High',
    issue: 'Irregular cardiac pattern',
    lastUpdate: '1 day ago',
    urgency: 'High',
  },
  {
    rank: 3,
    name: 'Emily Chen',
    risk: 'Moderate',
    issue: 'Glucose trending upward',
    lastUpdate: '2 days ago',
    urgency: 'Moderate',
  },
  {
    rank: 4,
    name: 'Robert Lopez',
    risk: 'Moderate',
    issue: 'Routine follow-up',
    lastUpdate: '3 days ago',
    urgency: 'Low',
  },
]

export default function ClinicalPage() {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Clinical Decision Support</h1>
        <p className="text-muted-foreground mt-2">AI-powered clinical insights and patient prioritization</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Critical Cases</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-destructive">2</div>
            <p className="text-xs text-destructive flex items-center gap-1 mt-1">
              <AlertTriangle className="h-3 w-3" /> Require immediate attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">High Risk</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-health-danger">5</div>
            <p className="text-xs text-health-danger mt-1">Follow-up recommended</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Stable Patients</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-health-success">17</div>
            <p className="text-xs text-health-success mt-1">Routine monitoring</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-primary">8</div>
            <p className="text-xs text-muted-foreground mt-1">Medical image analysis</p>
          </CardContent>
        </Card>
      </div>

      {/* Patient Prioritization List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Patient Prioritization List
          </CardTitle>
          <CardDescription>AI-ranked by clinical urgency</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {prioritizedPatients.map((patient) => (
              <div
                key={patient.rank}
                className={`p-4 border rounded-lg hover:bg-muted/50 transition-colors ${
                  patient.risk === 'Critical' ? 'border-destructive/50 bg-destructive/5' :
                  patient.risk === 'High' ? 'border-health-danger/50 bg-health-danger/5' :
                  'border-border'
                }`}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-4 sm:flex-1">
                    <div className="shrink-0">
                      <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center font-bold">
                        {patient.rank}
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="font-medium">{patient.name}</p>
                      <p className="text-sm text-muted-foreground mt-0.5">{patient.issue}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                    <div className="sm:text-right">
                      <Badge
                        className={
                          patient.risk === 'Critical' ? 'bg-destructive/10 text-destructive border-destructive/20' :
                          patient.risk === 'High' ? 'bg-health-danger/10 text-health-danger border-health-danger/20' :
                          patient.risk === 'Moderate' ? 'bg-health-warning/10 text-health-warning border-health-warning/20' :
                          'bg-health-success/10 text-health-success border-health-success/20'
                        }
                        variant="outline"
                      >
                        {patient.risk}
                      </Badge>
                      <p className="text-xs text-muted-foreground mt-2">{patient.lastUpdate}</p>
                    </div>
                    <Button variant="outline" size="sm">
                      Review
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Medical Image Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Medical Image Analysis Queue
          </CardTitle>
          <CardDescription>Pending radiology & pathology reviews</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
              <div className="aspect-square bg-muted rounded-lg mb-3 flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">Chest X-ray</p>
              <p className="text-xs text-muted-foreground mt-1">John Anderson • 2 hours ago</p>
              <div className="mt-3 flex gap-2">
                <Badge variant="outline" className="bg-health-warning/10 text-health-warning border-health-warning/20">
                  Pending
                </Badge>
                <Badge variant="outline">High Priority</Badge>
              </div>
            </div>

            <div className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
              <div className="aspect-square bg-muted rounded-lg mb-3 flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">Retinal Scan</p>
              <p className="text-xs text-muted-foreground mt-1">Emily Chen • 4 hours ago</p>
              <div className="mt-3 flex gap-2">
                <Badge variant="outline" className="bg-health-warning/10 text-health-warning border-health-warning/20">
                  Pending
                </Badge>
                <Badge variant="outline">Moderate Priority</Badge>
              </div>
            </div>

            <div className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
              <div className="aspect-square bg-muted rounded-lg mb-3 flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">ECG Waveform</p>
              <p className="text-xs text-muted-foreground mt-1">Michael Davis • 1 day ago</p>
              <div className="mt-3 flex gap-2">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  Reviewed
                </Badge>
                <Badge variant="outline">Abnormal</Badge>
              </div>
            </div>

            <div className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
              <div className="aspect-square bg-muted rounded-lg mb-3 flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">Blood Test Results</p>
              <p className="text-xs text-muted-foreground mt-1">Sarah Wilson • 1 day ago</p>
              <div className="mt-3 flex gap-2">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  Reviewed
                </Badge>
                <Badge variant="outline">Normal</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pre-Consultation Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Stethoscope className="h-5 w-5" />
            Pre-Consultation Summary
          </CardTitle>
          <CardDescription>Quick reference for upcoming consultations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 border border-border rounded-lg">
              <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-10 w-10">
                    <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=John" />
                    <AvatarFallback>JA</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">John Anderson</p>
                    <p className="text-xs text-muted-foreground">68y • Male</p>
                  </div>
                </div>
                <Clock className="h-5 w-5 text-primary" />
              </div>
              <div className="space-y-2 text-sm">
                <p><span className="font-medium">Chief Complaint:</span> Hypertension management</p>
                <p><span className="font-medium">Last 7 days:</span> Elevated readings (160-180 systolic)</p>
                <p><span className="font-medium">Current Meds:</span> Lisinopril 10mg, Amlodipine 5mg</p>
                <p><span className="font-medium">Recommendation:</span> Consider dosage adjustment + lifestyle review</p>
              </div>
            </div>

            <div className="p-4 border border-border rounded-lg">
              <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-10 w-10">
                    <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=Emily" />
                    <AvatarFallback>EC</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">Emily Chen</p>
                    <p className="text-xs text-muted-foreground">45y • Female</p>
                  </div>
                </div>
                <Clock className="h-5 w-5 text-health-warning" />
              </div>
              <div className="space-y-2 text-sm">
                <p><span className="font-medium">Chief Complaint:</span> Diabetes follow-up</p>
                <p><span className="font-medium">Last 7 days:</span> HbA1c trending up (slight increase)</p>
                <p><span className="font-medium">Current Meds:</span> Metformin 1000mg</p>
                <p><span className="font-medium">Recommendation:</span> Enhance dietary compliance + increase monitoring</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
