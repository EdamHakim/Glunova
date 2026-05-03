'use client'

import { useState, useRef, ChangeEvent, FormEvent } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Upload } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import RoleGuard from '@/components/auth/role-guard'
import { useAuth } from '@/components/auth-context'
import { getApiUrls } from '@/lib/auth'

interface TongueResult {
  probability: number
  prediction_label: string
  threshold_used: number
  heatmapBase64?: string
}

export default function TongueScreeningPage() {
  const { user, loading } = useAuth()
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string>('')
  const [result, setResult] = useState<TongueResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file')
      return
    }

    setImageFile(file)
    setError('')

    const reader = new FileReader()
    reader.onload = (event) => {
      setImagePreview(event.target?.result as string)
    }
    reader.readAsDataURL(file)
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!imageFile) {
      setError('Please select an image first')
      return
    }

    setIsLoading(true)
    setError('')

    try {
      if (!user) {
        throw new Error('User not authenticated')
      }

      const { fastapi } = getApiUrls()
      const formData = new FormData()
      formData.append('image', imageFile)

      const response = await fetch(`${fastapi}/screening/tongue/infer`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to analyze image')
      }

      const data = await response.json()
      setResult({
        probability: data.probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
      })

      // Try to get heatmap
      try {
        const heatmapResponse = await fetch(`${fastapi}/screening/tongue/gradcam`, {
          method: 'POST',
          credentials: 'include',
          body: formData,
        })
        if (heatmapResponse.ok) {
          const heatmapData = await heatmapResponse.json()
          if (heatmapData.heatmap_base64) {
            setResult((prev) => prev ? { ...prev, heatmapBase64: heatmapData.heatmap_base64 } : null)
          }
        }
      } catch {
        // Silently ignore heatmap errors
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze image')
      setResult(null)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClear = () => {
    setImageFile(null)
    setImagePreview('')
    setResult(null)
    setError('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

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
      description="Tongue screening is only available to patient and doctor accounts."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex items-center gap-2">
          <Link href="/dashboard/screening">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Tongue Screening</h1>
            <p className="text-muted-foreground mt-1">
              AI-powered diabetes risk assessment from tongue images
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Upload Tongue Image</CardTitle>
            <CardDescription>
              Take a clear photo of the tongue and upload for analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Upload Area */}
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors cursor-pointer"
                onClick={handleUploadClick}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <div className="space-y-2">
                  <Upload className="w-8 h-8 mx-auto text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">Click to upload</p>
                    <p className="text-xs text-gray-500">PNG, JPG up to 10MB</p>
                  </div>
                </div>
              </div>

              {/* Error */}
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Preview */}
              {imagePreview && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Selected Image</p>
                  <div className="relative w-full h-64 bg-gray-100 rounded-lg overflow-hidden">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              )}

              {/* Buttons */}
              <div className="flex gap-2 justify-end">
                {imageFile && (
                  <Button type="button" variant="outline" onClick={handleClear} disabled={isLoading}>
                    Clear
                  </Button>
                )}
                <Button type="submit" disabled={!imageFile || isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Analyzing...
                    </>
                  ) : (
                    'Analyze Image'
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Results */}
        {result && (
          <Card className="border-2 border-blue-200">
            <CardHeader>
              <CardTitle>Analysis Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-700">Prediction</p>
                  <p className="text-xl font-bold text-blue-600">{result.prediction_label}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-700">Probability</p>
                  <p className="text-xl font-bold text-orange-600">
                    {(result.probability * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Probability</p>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="h-3 rounded-full bg-blue-500 transition-all"
                    style={{ width: `${result.probability * 100}%` }}
                  />
                </div>
              </div>

              {result.heatmapBase64 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Explainability (Grad-CAM)</p>
                  <div className="relative w-full h-64 bg-gray-100 rounded-lg overflow-hidden">
                    <img
                      src={`data:image/jpeg;base64,${result.heatmapBase64}`}
                      alt="Grad-CAM Heatmap"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              )}

              <Button variant="outline" onClick={handleClear} className="w-full">
                Analyze Another Image
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Instructions */}
        <Card className="bg-blue-50 border-blue-200">
          <CardHeader>
            <CardTitle>Tips for Best Results</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              <li>Ensure good lighting when taking the photo</li>
              <li>Take a clear, close-up image of the tongue</li>
              <li>The entire tongue should be visible in the image</li>
              <li>Use a high-quality camera or smartphone</li>
              <li>Results are for screening purposes and should be confirmed by a healthcare professional</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}
