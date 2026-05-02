'use client'

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Upload, Mic, AlertCircle, StopCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getApiUrls } from '@/lib/auth'
import RoleGuard from '@/components/auth/role-guard'

type TongueResult = {
  probability: number
  prediction_label: string
  threshold_used: number
  heatmapBase64?: string
}

type VoiceShapSegment = {
  segment: number
  start_s: number
  end_s: number
  shap_value: number
  abs_shap: number
}

type VoiceResult = {
  probability: number
  raw_probability: number
  prediction_label: string
  threshold_used: number
  ood_flag: boolean
  shap_ready: boolean
  shap_message: string
  shap_base_value: number | null
  shap_segments: VoiceShapSegment[]
  shap_plot_base64: string | null
}

import { useAuth } from '@/components/auth-context'

export default function ScreeningPage() {
  const { user: sessionUser, loading: sessionLoading } = useAuth()

  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [voiceFile, setVoiceFile] = useState<File | null>(null)
  const [voicePreviewUrl, setVoicePreviewUrl] = useState('')
  const [voiceRecording, setVoiceRecording] = useState(false)
  const [voiceRecordingSeconds, setVoiceRecordingSeconds] = useState(0)
  const [loading, setLoading] = useState(false)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [error, setError] = useState('')
  const [tongueResult, setTongueResult] = useState<TongueResult | null>(null)
  const [voiceResult, setVoiceResult] = useState<VoiceResult | null>(null)
  const [isResultModalOpen, setIsResultModalOpen] = useState(false)
  const voiceRecorderRef = useRef<MediaRecorder | null>(null)
  const voiceChunksRef = useRef<BlobPart[]>([])
  const voiceStreamRef = useRef<MediaStream | null>(null)

  const riskPercent = useMemo(() => {
    const probs = [tongueResult?.probability, voiceResult?.probability].filter(
      (v): v is number => typeof v === 'number',
    )
    if (!probs.length) return 0
    return Math.round((probs.reduce((sum, v) => sum + v, 0) / probs.length) * 100)
  }, [tongueResult, voiceResult])

  useEffect(() => {
    if (!voiceRecording) return

    const timer = window.setInterval(() => {
      setVoiceRecordingSeconds((seconds) => seconds + 1)
    }, 1000)

    return () => window.clearInterval(timer)
  }, [voiceRecording])

  useEffect(() => {
    return () => {
      voiceRecorderRef.current?.stop()
      voiceStreamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  useEffect(() => {
    return () => {
      if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl)
    }
  }, [voicePreviewUrl])

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setFile(selected)
    setError('')
    setTongueResult(null)
    setPreviewUrl(selected ? URL.createObjectURL(selected) : '')
  }

  function onVoiceFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setVoiceFile(selected)
    setVoicePreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return selected ? URL.createObjectURL(selected) : ''
    })
    setVoiceResult(null)
    setError('')
  }

  async function startVoiceRecording() {
    setError('')
    setVoiceResult(null)

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Voice recording is not supported in this browser. Please upload an audio file instead.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : ''
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)

      voiceChunksRef.current = []
      voiceStreamRef.current = stream
      voiceRecorderRef.current = recorder
      setVoiceRecordingSeconds(0)

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) voiceChunksRef.current.push(event.data)
      }

      recorder.onstop = async () => {
        const type = recorder.mimeType || 'audio/webm'
        const blob = new Blob(voiceChunksRef.current, { type })
        let recordedFile = new File([blob], `voice-recording-${Date.now()}.webm`, { type })
        let previewBlob = blob

        try {
          recordedFile = await convertRecordedBlobToWavFile(blob)
          previewBlob = recordedFile
        } catch {
          // Fall back to the browser recording when WAV conversion is unavailable.
        }

        setVoiceFile(recordedFile)
        setVoicePreviewUrl((current) => {
          if (current) URL.revokeObjectURL(current)
          return URL.createObjectURL(previewBlob)
        })

        stream.getTracks().forEach((track) => track.stop())
        voiceStreamRef.current = null
        voiceRecorderRef.current = null
        voiceChunksRef.current = []
        setVoiceRecording(false)
      }

      recorder.start()
      setVoiceRecording(true)
    } catch (recordingError) {
      setVoiceRecording(false)
      setError(recordingError instanceof Error ? recordingError.message : 'Could not start voice recording.')
    }
  }

  function stopVoiceRecording() {
    const recorder = voiceRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
  }

  async function onTongueSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setTongueResult(null)

    if (!file) {
      setError('Please select an image before submitting.')
      return
    }

    if (!sessionUser) {
      setError('You must login first.')
      return
    }
    
    if (sessionUser.role !== 'patient' || sessionUser.userId == null) {
      setError('Screening is only available to patient accounts with a valid session.')
      return
    }

    setLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const payload = new FormData()
      payload.append('image', file)

      const response = await fetch(`${fastapi}/screening/tongue/infer`, {
        method: 'POST',
        credentials: 'include',
        body: payload,
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Tongue screening request failed.')
      }
      const data = await response.json()
      const result = {
        probability: data.probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
        heatmapBase64: undefined,
      }

      const gradcamPayload = new FormData()
      gradcamPayload.append('image', file)
      const gradcamResponse = await fetch(`${fastapi}/screening/tongue/gradcam`, {
        method: 'POST',
        credentials: 'include',
        body: gradcamPayload,
      })
      if (gradcamResponse.ok) {
        const gradcamData = await gradcamResponse.json()
        result.heatmapBase64 = gradcamData.heatmap_base64
      }

      setTongueResult(result)
      setIsResultModalOpen(true)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setLoading(false)
    }
  }

  async function onVoiceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setVoiceResult(null)

    if (!voiceFile) {
      setError('Please select an audio file before submitting.')
      return
    }
    if (!sessionUser) {
      setError('You must login first.')
      return
    }
    if (sessionUser.role !== 'patient' || sessionUser.userId == null) {
      setError('Screening is only available to patient accounts with a valid session.')
      return
    }

    setVoiceLoading(true)
    try {
      const { fastapi } = getApiUrls()
      const payload = new FormData()
      payload.append('audio', voiceFile)

      const response = await fetch(`${fastapi}/screening/voice/infer`, {
        method: 'POST',
        credentials: 'include',
        body: payload,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Voice screening request failed.')
      }
      const data = await response.json()
      setVoiceResult({
        probability: data.probability,
        raw_probability: data.raw_probability,
        prediction_label: data.prediction_label,
        threshold_used: data.threshold_used,
        ood_flag: Boolean(data.ood_flag),
        shap_ready: Boolean(data.shap_ready),
        shap_message: data.shap_message ?? '',
        shap_base_value: data.shap_base_value ?? null,
        shap_segments: Array.isArray(data.shap_segments) ? data.shap_segments : [],
        shap_plot_base64: data.shap_plot_base64 ?? null,
      })
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Request failed.')
    } finally {
      setVoiceLoading(false)
    }
  }

  if (sessionLoading) {
    return (
      <div className="space-y-6 p-4 sm:p-6">
        <p className="text-sm text-muted-foreground">Loading session…</p>
      </div>
    )
  }

  return (
    <RoleGuard
      allowedRoles={['patient']}
      title="Screening unavailable"
      description="Self-service screening is limited to patient accounts."
    >
      <div className="space-y-6 p-4 sm:p-6">
        <Dialog open={isResultModalOpen} onOpenChange={setIsResultModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Tongue Screening Result</DialogTitle>
              <DialogDescription>AI prediction for your screening (account #{sessionUser?.userId}).</DialogDescription>
            </DialogHeader>

            {tongueResult ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">Prediction</span>
                  <Badge>{tongueResult.prediction_label}</Badge>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">Probability</span>
                  <span className="font-semibold">{Math.round(tongueResult.probability * 100)}%</span>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm text-muted-foreground">Threshold Used</span>
                  <span className="font-semibold">{tongueResult.threshold_used}</span>
                </div>
                {tongueResult.heatmapBase64 ? (
                  <div className="rounded-lg border p-2">
                    <p className="text-sm text-muted-foreground mb-2">Grad-CAM Heatmap</p>
                    <img
                      src={`data:image/jpeg;base64,${tongueResult.heatmapBase64}`}
                      alt="Tongue Grad-CAM"
                      className="w-full h-48 object-cover rounded"
                    />
                  </div>
                ) : null}
              </div>
            ) : null}

            <DialogFooter>
              <Button onClick={() => setIsResultModalOpen(false)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Non-Invasive Screening</h1>
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
              <form className="space-y-3" onSubmit={onVoiceSubmit}>
                <Input type="file" accept="audio/*" onChange={onVoiceFileChange} />
                <div className="rounded-md border bg-muted/40 p-3">
                  <p className="text-xs text-muted-foreground">Best option: record an 18 s voice clip for best results.</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant={voiceRecording ? 'secondary' : 'outline'}
                    onClick={startVoiceRecording}
                    disabled={voiceRecording || voiceLoading}
                    className="gap-2"
                  >
                    <Mic className="h-4 w-4" />
                    Record
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={stopVoiceRecording}
                    disabled={!voiceRecording}
                    className="gap-2"
                  >
                    <StopCircle className="h-4 w-4" />
                    Stop
                  </Button>
                </div>
                {voiceRecording ? (
                  <p className="text-xs font-medium text-health-danger">Recording... {voiceRecordingSeconds}s</p>
                ) : null}
                {voiceFile ? (
                  <div className="space-y-2">
                    <p className="break-all text-xs text-muted-foreground">
                      Selected: <span className="font-medium">{voiceFile.name}</span>
                    </p>
                    {voicePreviewUrl ? <audio controls src={voicePreviewUrl} className="w-full" /> : null}
                  </div>
                ) : (
                  <div className="aspect-video bg-muted rounded-lg flex items-center justify-center border-2 border-dashed border-border">
                    <div className="text-center">
                      <Mic className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                      <p className="text-sm text-muted-foreground">Upload or record a voice clip</p>
                    </div>
                  </div>
                )}
                <Button type="submit" variant="outline" className="w-full" disabled={voiceLoading}>
                  {voiceLoading ? 'Analyzing voice...' : 'Run Voice Screening'}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Tongue Image */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Upload className="h-5 w-5 text-health-warning" />
                Tongue Image
              </CardTitle>
              <CardDescription>Upload and run PyTorch tongue diabetes inference</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col justify-center gap-4">
              <form className="space-y-3" onSubmit={onTongueSubmit}>
                <Input type="file" accept="image/*" onChange={onFileChange} required />

                {previewUrl ? (
                  <div className="rounded-lg border p-2">
                    <img src={previewUrl} alt="Tongue preview" className="h-36 w-full object-cover rounded" />
                  </div>
                ) : null}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? 'Analyzing...' : 'Run Tongue Screening'}
                </Button>
              </form>
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
                <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <span className="font-medium">Overall Risk Score</span>
                  <Badge className="text-lg px-3 py-1">{riskPercent}</Badge>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className="bg-linear-to-r from-health-success via-health-warning to-health-danger h-2 rounded-full"
                    style={{ width: `${riskPercent}%` }}
                  />
                </div>
                {tongueResult ? (
                  <p className="text-xs text-muted-foreground mt-2">
                    Tongue result: <span className="font-medium">{tongueResult.prediction_label}</span> (threshold {tongueResult.threshold_used})
                  </p>
                ) : voiceResult ? (
                  <p className="text-xs text-muted-foreground mt-2">
                    Voice result: <span className="font-medium">{voiceResult.prediction_label}</span> (threshold {voiceResult.threshold_used})
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground mt-2">Submit a voice clip or tongue image to get model prediction.</p>
                )}
              </div>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              {tongueResult ? (
                <div className="rounded-lg border p-3">
                  <p className="text-sm text-muted-foreground">Latest Tongue Result</p>
                  <p className="font-semibold mt-1">
                    {tongueResult.prediction_label} ({Math.round(tongueResult.probability * 100)}%)
                  </p>
                  <Button variant="link" className="px-0 h-auto mt-1" onClick={() => setIsResultModalOpen(true)}>
                    View full details
                  </Button>
                </div>
              ) : null}

              {voiceResult ? (
                <div className="rounded-lg border p-3">
                  <p className="text-sm text-muted-foreground">Latest Voice Result</p>
                  <p className="font-semibold mt-1">
                    {voiceResult.prediction_label} ({Math.round(voiceResult.probability * 100)}%)
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Raw {Math.round(voiceResult.raw_probability * 100)}% | Threshold {voiceResult.threshold_used}
                    {voiceResult.ood_flag ? ' | OOD flagged' : ''}
                  </p>
                </div>
              ) : null}

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground">Voice Analysis</p>
                  <p className="font-semibold text-health-success">
                    {voiceResult ? `${Math.round(voiceResult.probability * 100)}% ${voiceResult.prediction_label}` : 'Not analyzed yet'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {voiceResult
                      ? voiceResult.shap_ready
                        ? 'BYOL-S + SVM with SHAP segment attribution'
                        : voiceResult.shap_message || 'Prediction available without SHAP'
                      : 'Upload voice and run screening'}
                  </p>
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
                {voiceResult?.shap_ready && voiceResult.shap_segments.length ? (
                  <div className="bg-muted rounded-lg p-3 space-y-2 max-h-72 overflow-auto">
                    {voiceResult.shap_segments
                      .slice()
                      .sort((a, b) => b.abs_shap - a.abs_shap)
                      .slice(0, 8)
                      .map((segment) => {
                        const width = Math.min(100, Math.round(segment.abs_shap * 300))
                        const positive = segment.shap_value >= 0
                        return (
                          <div key={segment.segment} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span>
                                Seg {segment.segment} ({segment.start_s.toFixed(1)}s-{segment.end_s.toFixed(1)}s)
                              </span>
                              <span className={positive ? 'text-health-danger' : 'text-health-success'}>
                                {segment.shap_value.toFixed(3)}
                              </span>
                            </div>
                            <div className="h-2 bg-background rounded">
                              <div
                                className={`h-2 rounded ${positive ? 'bg-health-danger' : 'bg-health-success'}`}
                                style={{ width: `${Math.max(4, width)}%` }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                ) : (
                  <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                    <p className="text-xs text-center text-muted-foreground">
                      Run voice screening to generate SHAP segment attribution
                    </p>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <p className="font-medium text-sm">Tongue Image</p>
                {tongueResult?.heatmapBase64 ? (
                  <div className="bg-muted rounded-lg p-2 aspect-square">
                    <img
                      src={`data:image/jpeg;base64,${tongueResult.heatmapBase64}`}
                      alt="Tongue Grad-CAM heatmap"
                      className="h-full w-full rounded object-cover"
                    />
                  </div>
                ) : (
                  <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                    <p className="text-xs text-center text-muted-foreground">
                      Run tongue screening to generate Grad-CAM heatmap
                    </p>
                  </div>
                )}
              </div>
              <div className="space-y-2 md:col-span-2">
                <p className="font-medium text-sm">Feature Importance (SHAP)</p>
                {voiceResult?.shap_ready && voiceResult.shap_plot_base64 ? (
                  <div className="bg-muted rounded-lg p-2">
                    <img
                      src={`data:image/png;base64,${voiceResult.shap_plot_base64}`}
                      alt="Waveform with SHAP segment overlay"
                      className="w-full rounded object-contain"
                    />
                  </div>
                ) : voiceResult?.shap_ready && voiceResult.shap_segments.length && voiceFile ? (
                  <VoiceShapWaveform audioFile={voiceFile} segments={voiceResult.shap_segments} />
                ) : (
                  <div className="bg-muted rounded-lg p-3 aspect-square flex items-center justify-center">
                    <p className="text-xs text-center text-muted-foreground">
                      Feature contribution chart
                    </p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  )
}

function VoiceShapWaveform({
  audioFile,
  segments,
}: {
  audioFile: File
  segments: VoiceShapSegment[]
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [drawError, setDrawError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function drawWaveform() {
      const canvas = canvasRef.current
      if (!canvas) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      try {
        setDrawError('')
        const audioContext = new AudioContext()
        const buffer = await audioFile.arrayBuffer()
        const decoded = await audioContext.decodeAudioData(buffer.slice(0))
        await audioContext.close()

        if (cancelled) return

        const width = canvas.width
        const height = canvas.height
        const topHeight = Math.round(height * 0.56)
        const chartTop = topHeight + 44
        const chartHeight = height - chartTop - 30
        const data = decoded.getChannelData(0)
        const duration = decoded.duration || Math.max(...segments.map((segment) => segment.end_s), 1)
        const maxAbsShap = Math.max(1e-8, ...segments.map((segment) => Math.abs(segment.shap_value)))

        ctx.clearRect(0, 0, width, height)
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)

        ctx.fillStyle = '#1f2937'
        ctx.font = '600 20px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Waveform With SHAP Segment Overlay', width / 2, 28)

        for (const segment of segments) {
          const x = (segment.start_s / duration) * width
          const w = Math.max(1, ((segment.end_s - segment.start_s) / duration) * width)
          const alpha = 0.18 + Math.min(0.32, Math.abs(segment.shap_value) / maxAbsShap * 0.32)
          ctx.fillStyle = segment.shap_value >= 0 ? `rgba(220, 38, 38, ${alpha})` : `rgba(37, 99, 235, ${alpha})`
          ctx.fillRect(x, 44, w, topHeight - 52)
        }

        ctx.strokeStyle = '#111827'
        ctx.lineWidth = 1
        ctx.beginPath()
        const samplesPerPixel = Math.max(1, Math.floor(data.length / width))
        const centerY = 44 + (topHeight - 52) / 2
        const ampScale = (topHeight - 62) / 2
        for (let x = 0; x < width; x += 1) {
          let min = 1
          let max = -1
          const start = x * samplesPerPixel
          const end = Math.min(data.length, start + samplesPerPixel)
          for (let i = start; i < end; i += 1) {
            const value = data[i]
            if (value < min) min = value
            if (value > max) max = value
          }
          ctx.moveTo(x, centerY + min * ampScale)
          ctx.lineTo(x, centerY + max * ampScale)
        }
        ctx.stroke()

        ctx.strokeStyle = '#d1d5db'
        ctx.beginPath()
        ctx.moveTo(0, centerY)
        ctx.lineTo(width, centerY)
        ctx.stroke()

        ctx.fillStyle = '#1f2937'
        ctx.font = '600 18px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('SHAP Value By Time Segment', width / 2, chartTop - 12)

        const maxPositive = Math.max(1e-8, ...segments.map((segment) => Math.max(0, segment.shap_value)))
        const zeroY = chartTop + chartHeight
        for (const segment of segments) {
          const x = (segment.start_s / duration) * width
          const w = Math.max(2, ((segment.end_s - segment.start_s) / duration) * width * 0.92)
          const h = Math.max(2, Math.abs(segment.shap_value) / maxPositive * chartHeight)
          ctx.fillStyle = segment.shap_value >= 0 ? '#c81e35' : '#2563eb'
          ctx.fillRect(x + 2, zeroY - h, w, h)
        }

        ctx.strokeStyle = '#111827'
        ctx.beginPath()
        ctx.moveTo(0, zeroY)
        ctx.lineTo(width, zeroY)
        ctx.stroke()

        ctx.fillStyle = '#374151'
        ctx.font = '13px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Time (s)', width / 2, height - 6)
      } catch (error) {
        setDrawError(error instanceof Error ? error.message : 'Could not draw waveform chart.')
      }
    }

    drawWaveform()

    return () => {
      cancelled = true
    }
  }, [audioFile, segments])

  return (
    <div className="bg-muted rounded-lg p-2">
      <canvas
        ref={canvasRef}
        width={1200}
        height={520}
        className="w-full rounded bg-background"
        aria-label="Waveform with SHAP segment overlay"
      />
      {drawError ? <p className="mt-2 text-xs text-destructive">{drawError}</p> : null}
    </div>
  )
}

async function convertRecordedBlobToWavFile(blob: Blob): Promise<File> {
  const audioContext = new AudioContext()
  try {
    const decoded = await audioContext.decodeAudioData(await blob.arrayBuffer())
    const wavBlob = audioBufferToWavBlob(decoded)
    return new File([wavBlob], `voice-recording-${Date.now()}.wav`, { type: 'audio/wav' })
  } finally {
    await audioContext.close()
  }
}

function audioBufferToWavBlob(buffer: AudioBuffer): Blob {
  const channel = buffer.getChannelData(0)
  const sampleRate = buffer.sampleRate
  const dataLength = channel.length * 2
  const arrayBuffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(arrayBuffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, dataLength, true)

  let offset = 44
  for (let i = 0; i < channel.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, channel[i]))
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
    offset += 2
  }

  return new Blob([arrayBuffer], { type: 'audio/wav' })
}

function writeAscii(view: DataView, offset: number, text: string) {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i))
  }
}
