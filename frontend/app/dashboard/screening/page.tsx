import { Upload, Mic, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export default function ScreeningPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Non-Invasive Screening</h1>
        <p className="text-muted-foreground mt-2">AI-powered health assessment using voice, tongue, and eye imaging</p>
      </div>

      {/* Upload Sections */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Voice Recording */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mic className="h-5 w-5 text-health-info" />
              Voice Recording
            </CardTitle>
            <CardDescription>Record patient voice sample</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border">
              <div className="text-center">
                <Mic className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Click to record</p>
              </div>
            </div>
            <Button variant="outline" className="w-full">
              Start Recording
            </Button>
          </CardContent>
        </Card>

        {/* Tongue Image */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Upload className="h-5 w-5 text-health-warning" />
              Tongue Image
            </CardTitle>
            <CardDescription>Upload tongue photo</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border hover:border-primary cursor-pointer transition-colors">
              <div className="text-center">
                <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Drag or click to upload</p>
              </div>
            </div>
            <Button variant="outline" className="w-full">
              Upload Image
            </Button>
          </CardContent>
        </Card>

        {/* Eye Image */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Upload className="h-5 w-5 text-health-success" />
              Eye Image
            </CardTitle>
            <CardDescription>Upload eye/retina photo</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center gap-4">
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border hover:border-primary cursor-pointer transition-colors">
              <div className="text-center">
                <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Drag or click to upload</p>
              </div>
            </div>
            <Button variant="outline" className="w-full">
              Upload Image
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* AI Predictions */}
      <Card>
        <CardHeader>
          <CardTitle>AI Assessment Results</CardTitle>
          <CardDescription>Predictions from multi-modal analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 border border-border rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">Overall Risk Score</span>
                <Badge className="text-lg px-3 py-1">45</Badge>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-health-success via-health-warning to-health-danger h-2 rounded-full"
                  style={{ width: '45%' }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2">Moderate risk - Recommend monitoring</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Voice Analysis</p>
                <p className="font-semibold text-health-success">Low Risk</p>
                <p className="text-xs text-muted-foreground mt-1">Normal respiratory pattern</p>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Tongue Examination</p>
                <p className="font-semibold text-health-warning">Moderate</p>
                <p className="text-xs text-muted-foreground mt-1">Slight coating detected</p>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Eye Examination</p>
                <p className="font-semibold text-health-danger">Requires Review</p>
                <p className="text-xs text-muted-foreground mt-1">Consult ophthalmologist</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Explainability */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            AI Explainability
          </CardTitle>
          <CardDescription>Grad-CAM & SHAP analysis of predictions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <p className="font-medium text-sm">Voice Features</p>
              <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                <p className="text-xs text-center text-muted-foreground">
                  Grad-CAM heatmap visualization
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-sm">Tongue Image</p>
              <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                <p className="text-xs text-center text-muted-foreground">
                  Region importance map
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-sm">Feature Importance (SHAP)</p>
              <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                <p className="text-xs text-center text-muted-foreground">
                  Feature contribution chart
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
