'use client'

import { useState, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { inferCataract, CataractInferenceResponse } from '@/lib/screening-api'
import { AlertCircle, Eye, Upload, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react'

const CATARACT_GRADES = {
  0: { label: 'No Cataract', color: 'bg-green-100', textColor: 'text-green-800' },
  1: { label: 'Early Cataract', color: 'bg-yellow-100', textColor: 'text-yellow-800' },
  2: { label: 'Moderate Cataract', color: 'bg-orange-100', textColor: 'text-orange-800' },
  3: { label: 'Severe Cataract', color: 'bg-red-100', textColor: 'text-red-800' },
}

export function CataractDetectionPanel() {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string>('')
  const [result, setResult] = useState<CataractInferenceResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file')
      return
    }

    setImageFile(file)
    setError('')

    // Create preview
    const reader = new FileReader()
    reader.onload = (event) => {
      setImagePreview(event.target?.result as string)
    }
    reader.readAsDataURL(file)
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleInfer = async () => {
    if (!imageFile) {
      setError('Please select an image first')
      return
    }

    setLoading(true)
    setError('')
    try {
      const response = await inferCataract(imageFile)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze image')
      setResult(null)
    } finally {
      setLoading(false)
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

  const gradeInfo = result ? CATARACT_GRADES[result.prediction_index as keyof typeof CATARACT_GRADES] : null

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5" />
            <div>
              <CardTitle>Cataract Detection</CardTitle>
              <CardDescription>Upload an eye image for AI-assisted cataract severity assessment</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* File Upload Area */}
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors cursor-pointer"
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
                <p className="text-sm font-medium text-gray-900">Click to upload or drag and drop</p>
                <p className="text-xs text-gray-500">PNG, JPG, GIF up to 10MB</p>
              </div>
            </div>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Image Preview */}
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

          {/* Action Buttons */}
          <div className="flex gap-2 justify-end">
            {imageFile && (
              <Button
                variant="outline"
                onClick={handleClear}
                disabled={loading}
              >
                Clear
              </Button>
            )}
            <Button
              onClick={handleInfer}
              disabled={!imageFile || loading}
              className="gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Eye className="w-4 h-4" />
                  Analyze Image
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <Card className="border-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {result.prediction_index === 0 ? (
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-orange-600" />
              )}
              Analysis Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Severity Grade */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Severity Grade</p>
              <div className={`p-4 rounded-lg ${gradeInfo?.color || 'bg-gray-100'} text-center`}>
                <p className={`text-lg font-bold ${gradeInfo?.textColor || 'text-gray-800'}`}>
                  {gradeInfo?.label}
                </p>
                <p className="text-sm text-gray-600">Grade {result.prediction_index} / 3</p>
              </div>
            </div>

            {/* Confidence */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Confidence</p>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-2xl font-bold text-blue-600">
                    {(result.confidence * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Cataract Probability</p>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-2xl font-bold text-orange-600">
                    {(result.p_cataract * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Detailed Probabilities */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Detailed Predictions</p>
              <div className="space-y-2">
                {Object.entries(result.probabilities).map(([grade, prob]) => {
                  const gradeNum = parseInt(grade)
                  const gradeLabel = CATARACT_GRADES[gradeNum as keyof typeof CATARACT_GRADES]?.label || `Grade ${grade}`
                  const percentage = (prob * 100).toFixed(1)
                  const barWidth = `${prob * 100}%`

                  return (
                    <div key={grade} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{gradeLabel}</span>
                        <span className="text-gray-600">{percentage}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            gradeNum === 0
                              ? 'bg-green-500'
                              : gradeNum === 1
                              ? 'bg-yellow-500'
                              : gradeNum === 2
                              ? 'bg-orange-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: barWidth }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Model Info */}
            <div className="text-xs text-gray-500 space-y-1 border-t pt-3">
              <p>Model: {result.model_name}</p>
              <p>Version: {result.model_version}</p>
            </div>

            {/* Clear Button */}
            <Button
              variant="outline"
              onClick={handleClear}
              className="w-full"
            >
              Analyze Another Image
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
