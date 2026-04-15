import { AlertCircle, TrendingDown, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import HealthTrendChart from '@/components/dashboard/health-trend-chart'
import PatientSummary from '@/components/dashboard/patient-summary'

export default function Dashboard() {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Dashboard</h1>
        <p className="text-muted-foreground mt-2">Welcome back, Dr. Sarah. Here&apos;s your patient overview.</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Patients</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">24</div>
            <p className="text-xs text-health-success flex items-center gap-1 mt-1">
              <TrendingUp className="h-3 w-3" /> 12% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending Screenings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-health-warning">8</div>
            <p className="text-xs text-muted-foreground mt-1">Due within 7 days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-health-danger">3</div>
            <p className="text-xs text-health-danger flex items-center gap-1 mt-1">
              <AlertCircle className="h-3 w-3" /> Requires attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Risk Score (Avg)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">42</div>
            <p className="text-xs text-muted-foreground mt-1">Moderate risk</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Health Progression</CardTitle>
            <CardDescription>Patient risk scores over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <HealthTrendChart />
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button className="w-full justify-start" variant="outline">
              New Screening
            </Button>
            <Button className="w-full justify-start" variant="outline">
              View Alerts
            </Button>
            <Button className="w-full justify-start" variant="outline">
              Log Meal
            </Button>
            <Button className="w-full justify-start" variant="outline">
              Psychology Session
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Patient Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Patients</CardTitle>
          <CardDescription>Latest patient assessments and status</CardDescription>
        </CardHeader>
        <CardContent>
          <PatientSummary />
        </CardContent>
      </Card>
    </div>
  )
}
