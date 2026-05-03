'use client'

import Link from 'next/link'
import { useAuth } from '@/components/auth-context'
import RoleGuard from '@/components/auth/role-guard'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Eye, Mic, ScanSearch, ArrowRight } from 'lucide-react'

export default function ScreeningMainPage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  return (
    <RoleGuard
      allowedRoles={['patient', 'doctor']}
      title="Screening unavailable"
      description="Screening is only available to patient and doctor accounts."
    >
      <div className="space-y-8 p-4 sm:p-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Non-Invasive Screening</h1>
          <p className="mt-2 text-lg text-muted-foreground">
            AI-powered health assessment using voice, tongue, and eye imaging
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {/* Voice Recording */}
          <Card className="flex flex-col overflow-hidden hover:shadow-lg transition-shadow">
            <CardHeader className="bg-gradient-to-br from-blue-50 to-cyan-50">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Mic className="w-5 h-5 text-blue-600" />
                    Voice Recording
                  </CardTitle>
                  <CardDescription>Analyze vocal patterns</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 pt-6 flex flex-col justify-between">
              <p className="text-sm text-gray-600 mb-4">
                Record a voice sample for AI analysis of vocal biomarkers related to diabetes risk factors.
              </p>
              <Button disabled className="w-full gap-2">
                Coming Soon <ArrowRight className="w-4 h-4" />
              </Button>
            </CardContent>
          </Card>

          {/* Tongue Image */}
          <Card className="flex flex-col overflow-hidden hover:shadow-lg transition-shadow">
            <CardHeader className="bg-gradient-to-br from-purple-50 to-pink-50">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <ScanSearch className="w-5 h-5 text-purple-600" />
                    Tongue Image
                  </CardTitle>
                  <CardDescription>Tongue diabetes assessment</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 pt-6 flex flex-col justify-between">
              <p className="text-sm text-gray-600 mb-4">
                Upload a tongue image for PyTorch-based inference to assess diabetes risk using tongue characteristics.
              </p>
              <Link href="/dashboard/screening/tongue" className="w-full">
                <Button className="w-full gap-2">
                  Start Screening <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Cataract Image */}
          <Card className="flex flex-col overflow-hidden hover:shadow-lg transition-shadow md:col-span-1 lg:col-span-1">
            <CardHeader className="bg-gradient-to-br from-amber-50 to-orange-50">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Eye className="w-5 h-5 text-amber-600" />
                    Cataract Detection
                  </CardTitle>
                  <CardDescription>Eye health assessment</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 pt-6 flex flex-col justify-between">
              <p className="text-sm text-gray-600 mb-4">
                Upload an eye image for AI-powered cataract severity classification across 4 severity grades.
              </p>
              <Link href="/dashboard/screening/cataract" className="w-full">
                <Button className="w-full gap-2">
                  Start Detection <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Information Section */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold">How Screening Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">1. Prepare Image</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">
                  Take a clear, well-lit image of the body part being screened (tongue or eye).
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">2. Upload & Analyze</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">
                  Upload the image and run the AI model for instant analysis and prediction.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">3. View Results</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">
                  Review predictions, confidence scores, and explainability visualizations (Grad-CAM).
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Privacy Notice */}
        <Card className="border-l-4 border-l-blue-500 bg-blue-50">
          <CardHeader>
            <CardTitle className="text-base">Privacy & Data Usage</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-700">
            <p>
              Your screening results are securely processed and stored in your medical record. AI predictions are for clinical support only and do not replace medical diagnosis. Always consult with a healthcare professional for medical decisions.
            </p>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}
