'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageCircle, BarChart3, Heart, Zap, AlertTriangle, Video, Mic, CameraOff } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import {
  acknowledgeCrisisEvent,
  clearPhysicianSessionGate,
  endPsychologySession,
  getPsychologyTrends,
  listCrisisEvents,
  psychologyWsBase,
  sendPsychologyMessage,
  startPsychologySession,
  type CrisisEvent,
  type PsychologyMessageResult,
  type TrendPoint,
} from '@/lib/psychology-api'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type ChatBubble = {
  role: 'patient' | 'assistant'
  content: string
}

type LiveEmotion = {
  label: string
  confidence: number
  distress_score: number
  timestamp: string
}

function getErrorMessage(error: unknown): string {
  const fallback = 'Could not start session.'
  if (error instanceof Error && error.message) {
    const raw = error.message.trim()
    if (!raw) return fallback
    try {
      const parsed = JSON.parse(raw) as { detail?: string }
      if (parsed?.detail && typeof parsed.detail === 'string') return parsed.detail
    } catch {
      // Non-JSON error payload; use raw message.
    }
    return raw
  }
  return fallback
}

export default function PsychologyPage() {
  const { user } = useAuth()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionBlocked, setSessionBlocked] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [chat, setChat] = useState<ChatBubble[]>([])
  const [latestResult, setLatestResult] = useState<PsychologyMessageResult | null>(null)
  const [trends, setTrends] = useState<TrendPoint[]>([])
  const [crisisEvents, setCrisisEvents] = useState<CrisisEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [liveEmotion, setLiveEmotion] = useState<LiveEmotion | null>(null)
  const [micListening, setMicListening] = useState(false)
  const [startingSession, setStartingSession] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const captureTimerRef = useRef<number | null>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const role = user?.role
  const isPatient = role === 'patient'
  const isDoctor = role === 'doctor'
  const intro = isDoctor
    ? 'Review emotional trends and support signals for assigned patients.'
    : role === 'caregiver'
      ? 'Follow wellness status and support recommendations without exposing private therapy details.'
      : 'AI-powered emotional health tracking and therapy sessions.'
  const patientId = useMemo(() => {
    const fromSession = user?.userId
    if (typeof fromSession === 'number' && Number.isFinite(fromSession) && fromSession > 0) return fromSession
    const parsed = Number(user?.id || 0)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
  }, [user?.id, user?.userId])

  const ensureSessionStarted = useCallback(async (forceNew = false) => {
    if (!patientId) return null
    if (!forceNew && sessionId) return sessionId
    setStartingSession(true)
    try {
      const payload = await startPsychologySession(patientId, 'en')
      if (payload.allowed === false || !payload.session_id) {
        setSessionBlocked(payload.block_reason || 'Could not start session.')
        setSessionId(null)
        return null
      }
      setSessionBlocked(null)
      setSessionId(payload.session_id)
      return payload.session_id
    } catch (error) {
      setSessionBlocked(getErrorMessage(error))
      setSessionId(null)
      return null
    } finally {
      setStartingSession(false)
    }
  }, [patientId, sessionId])

  useEffect(() => {
    if (!patientId) return
    let cancelled = false
    void startPsychologySession(patientId, 'en')
      .then((payload) => {
        if (cancelled) return
        if (payload.allowed === false) {
          setSessionId(null)
          setSessionBlocked(payload.block_reason || 'Session not available.')
          return
        }
        setSessionBlocked(null)
        setSessionId(payload.session_id)
      })
      .catch((error) => {
        if (!cancelled) {
          setSessionId(null)
          setSessionBlocked(getErrorMessage(error))
        }
      })
    return () => {
      cancelled = true
    }
  }, [patientId])

  useEffect(() => {
    if (!patientId) return
    let cancelled = false
    void getPsychologyTrends(patientId)
      .then((payload) => {
        if (!cancelled) setTrends(payload.points)
      })
      .catch(() => {
        if (!cancelled) setTrends([])
      })
    if (isDoctor) {
      void listCrisisEvents(undefined)
        .then((items) => {
          if (!cancelled) setCrisisEvents(items)
        })
        .catch(() => {
          if (!cancelled) setCrisisEvents([])
        })
    } else {
      setCrisisEvents([])
    }
    return () => {
      cancelled = true
    }
  }, [patientId, isDoctor])

  const stopCamera = useCallback(() => {
    if (captureTimerRef.current != null) {
      window.clearInterval(captureTimerRef.current)
      captureTimerRef.current = null
    }
    wsRef.current?.close()
    wsRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
    setLiveEmotion(null)
  }, [])

  const startCamera = useCallback(async () => {
    if (!patientId || !isPatient) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }
      const wsUrl = `${psychologyWsBase()}${process.env.NEXT_PUBLIC_PSYCHOLOGY_PREFIX || '/psychology'}/ws/emotion/${patientId}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(String(ev.data)) as LiveEmotion
          setLiveEmotion(data)
        } catch {
          /* ignore */
        }
      }
      const canvas = document.createElement('canvas')
      const w = 320
      const h = 240
      canvas.width = w
      canvas.height = h
      const tick = () => {
        const vid = videoRef.current
        const socket = wsRef.current
        if (!vid || !socket || socket.readyState !== WebSocket.OPEN) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(vid, 0, 0, w, h)
        const frame = canvas.toDataURL('image/jpeg', 0.55)
        socket.send(JSON.stringify({ frame_base64: frame }))
      }
      captureTimerRef.current = window.setInterval(tick, 500)
      setCameraOn(true)
    } catch {
      setCameraOn(false)
    }
  }, [isPatient, patientId])

  useEffect(() => () => stopCamera(), [stopCamera])

  const toggleMic = useCallback(() => {
    const SR = typeof window !== 'undefined' && (window.SpeechRecognition || (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition)
    if (!SR) return
    if (micListening) {
      recognitionRef.current?.stop()
      recognitionRef.current = null
      setMicListening(false)
      return
    }
    const rec = new SR()
    rec.lang = 'fr-FR'
    rec.interimResults = false
    rec.continuous = false
    rec.onresult = (event) => {
      const text = event.results[0]?.[0]?.transcript?.trim()
      if (text) setInput((prev) => (prev ? `${prev} ${text}` : text))
    }
    rec.onend = () => {
      setMicListening(false)
      recognitionRef.current = null
    }
    recognitionRef.current = rec
    rec.start()
    setMicListening(true)
  }, [micListening])

  const stressPercent = useMemo(() => {
    if (!latestResult) return 25
    return Math.round(Math.max(0, Math.min(100, latestResult.distress_score * 100)))
  }, [latestResult])

  const chartData = useMemo(
    () =>
      trends.map((p, i) => ({
        name: `${i + 1}`,
        distress: Math.round(p.distress_score * 100),
        state: p.state,
      })),
    [trends],
  )

  async function submitMessage() {
    if (!input.trim()) return
    if (!patientId) {
      setChatError('Your patient profile is not loaded yet. Refresh the page and try again.')
      return
    }
    setChatError(null)
    const activeSessionId = await ensureSessionStarted()
    if (!activeSessionId) {
      setChatError(sessionBlocked || 'Could not start a therapy session. Please try again in a moment.')
      return
    }
    const patientText = input.trim()
    setInput('')
    setChat((old) => [...old, { role: 'patient', content: patientText }])
    setLoading(true)
    try {
      let result: PsychologyMessageResult
      try {
        result = await sendPsychologyMessage({ session_id: activeSessionId, patient_id: patientId, text: patientText })
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const likelySessionIssue = /session|404|403|not found|invalid/i.test(message)
        if (!likelySessionIssue) throw error
        const refreshedSessionId = await ensureSessionStarted(true)
        if (!refreshedSessionId) throw error
        result = await sendPsychologyMessage({ session_id: refreshedSessionId, patient_id: patientId, text: patientText })
      }
      setLatestResult(result)
      setChat((old) => [...old, { role: 'assistant', content: result.reply }])
      try {
        const trendPayload = await getPsychologyTrends(patientId)
        setTrends(trendPayload.points)
      } catch {
        /* non-fatal refresh failure */
      }
      if (result.crisis_detected && isDoctor) {
        try {
          const events = await listCrisisEvents(undefined)
          setCrisisEvents(events)
        } catch {
          /* non-fatal refresh failure */
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setChatError('Message was not sent. Please try again.')
      setChat((old) => [...old, { role: 'assistant', content: `I could not process that message right now (${message.slice(0, 120)}). Please retry.` }])
    } finally {
      setLoading(false)
    }
  }

  async function closeSession() {
    if (!sessionId || !patientId) return
    await endPsychologySession(sessionId, patientId)
    setSessionId(null)
  }

  async function onAckCrisis(ev: CrisisEvent) {
    try {
      await acknowledgeCrisisEvent(ev.id, isDoctor ? undefined : patientId)
      const items = await listCrisisEvents(isDoctor ? undefined : patientId)
      setCrisisEvents(items)
    } catch {
      /* noop */
    }
  }

  async function onClearGate(pid: number) {
    try {
      await clearPhysicianSessionGate(pid)
      const items = await listCrisisEvents(isDoctor ? undefined : patientId)
      setCrisisEvents(items)
      if (isPatient && pid === patientId) {
        const payload = await startPsychologySession(pid, 'en')
        if (payload.allowed && payload.session_id) {
          setSessionBlocked(null)
          setSessionId(payload.session_id)
        }
      }
    } catch {
      /* noop */
    }
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Psychology & Mental Wellness</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
        {sessionBlocked && (
          <div className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {sessionBlocked}
          </div>
        )}
        {latestResult?.physician_review_required && !sessionBlocked && (
          <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm">
            Physician review is active for this account. New AI sessions may be blocked until a clinician clears the gate.
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Current Mood</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-full bg-psychology-soft-purple/20 flex items-center justify-center">
                <Heart className="h-6 w-6 text-psychology-soft-purple" />
              </div>
              <div>
                <p className="text-lg font-bold">{liveEmotion?.label ?? latestResult?.mental_state ?? 'Neutral'}</p>
                <p className="text-xs text-muted-foreground">
                  {liveEmotion ? `Live · ${Math.round((liveEmotion.confidence ?? 0) * 100)}% conf` : 'Current detected emotional state'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Stress Level</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-health-warning">
                {liveEmotion ? Math.round(liveEmotion.distress_score * 100) : stressPercent}%
              </div>
              <div className="flex-1">
                <Progress value={liveEmotion ? liveEmotion.distress_score * 100 : stressPercent} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1">Distress score from multimodal fusion or camera stream</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Sleep Quality</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-health-success">{Math.max(5.5, 8.5 - stressPercent / 40).toFixed(1)}h</div>
              <div className="flex-1">
                <Badge variant="outline" className="bg-health-success/10 text-health-success border-health-success/20">
                  Inferred recovery indicator
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Wellness Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-3xl font-bold text-primary">{100 - stressPercent}</div>
              <div className="flex-1">
                <Progress value={100 - stressPercent} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1">Overall wellness estimate</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {isPatient && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Video className="h-4 w-4" />
              Camera & voice capture
            </CardTitle>
            <CardDescription>Stream face frames to the emotion WebSocket (2 fps). Use the mic for speech-to-text (browser).</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <video ref={videoRef} className="h-36 w-48 rounded-md border bg-black object-cover" playsInline muted />
            <div className="flex flex-col gap-2">
              <Button type="button" variant={cameraOn ? 'secondary' : 'default'} size="sm" onClick={() => (cameraOn ? stopCamera() : void startCamera())}>
                {cameraOn ? (
                  <>
                    <CameraOff className="mr-2 h-4 w-4" /> Stop camera
                  </>
                ) : (
                  <>
                    <Video className="mr-2 h-4 w-4" /> Start camera + stream
                  </>
                )}
              </Button>
              <Button type="button" variant={micListening ? 'secondary' : 'outline'} size="sm" onClick={() => toggleMic()}>
                <Mic className="mr-2 h-4 w-4" />
                {micListening ? 'Stop microphone' : 'Speech to text (FR)'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5 text-psychology-soft-purple" />
              {isPatient ? 'AI Therapy Session' : isDoctor ? 'Clinical Wellness Summary' : 'Support Summary'}
            </CardTitle>
            <CardDescription>
              {isPatient
                ? 'Chat with your AI therapist'
                : isDoctor
                  ? 'Read-only signals and patterns for follow-up planning'
                  : 'High-level wellness guidance appropriate for caregiver access'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isPatient ? (
              <div className="h-80 border border-border rounded-lg bg-muted/30 p-4 flex flex-col">
                <div className="flex-1 space-y-4 overflow-y-auto mb-4">
                  {chat.length === 0 && (
                    <div className="flex justify-start">
                      <div className="bg-psychology-soft-purple/10 text-psychology-soft-purple px-4 py-2 rounded-lg max-w-xs">
                        <p className="text-sm">How are you feeling right now? I can support you with a short CBT check-in.</p>
                      </div>
                    </div>
                  )}
                  {chat.map((entry, idx) => (
                    <div key={idx} className={entry.role === 'assistant' ? 'flex justify-start' : 'flex justify-end'}>
                      <div
                        className={
                          entry.role === 'assistant'
                            ? 'bg-psychology-soft-purple/10 text-psychology-soft-purple px-4 py-2 rounded-lg max-w-xs'
                            : 'bg-primary text-primary-foreground px-4 py-2 rounded-lg max-w-xs'
                        }
                      >
                        <p className="text-sm">{entry.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Share your thoughts..."
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        void submitMessage()
                      }
                    }}
                  />
                  <Button size="icon" onClick={() => void submitMessage()} disabled={loading || startingSession || !input.trim()}>
                    <MessageCircle className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" onClick={() => void closeSession()} disabled={!sessionId || startingSession}>
                    End
                  </Button>
                </div>
                {chatError && <p className="mt-2 text-xs text-destructive">{chatError}</p>}
              </div>
            ) : (
              <div className="rounded-lg border border-border bg-muted/30 p-4">
                <p className="font-medium">{isDoctor ? 'Private transcripts are hidden here' : 'Therapy details are not shared with caregivers'}</p>
                <p className="text-sm text-muted-foreground mt-2">
                  {isDoctor
                    ? 'You can use trends, scores, and support-needed flags for follow-up, while direct therapy conversation content stays patient-facing.'
                    : 'You can help with routines and encouragement, but private therapy chat content and detailed distress analysis stay restricted.'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Quick Wellness
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3" disabled>
              <div>
                <p className="font-medium text-sm">Guided Meditation</p>
                <p className="text-xs text-muted-foreground">10 min • Stress relief</p>
              </div>
            </Button>
            <Button variant="outline" className="w-full justify-start text-left h-auto py-3" disabled>
              <div>
                <p className="font-medium text-sm">Deep Breathing</p>
                <p className="text-xs text-muted-foreground">5 min • Instant calm</p>
              </div>
            </Button>
            {latestResult?.recommendation && (
              <div className="rounded-md border border-border p-3 text-sm text-muted-foreground">
                Recommended now: <span className="font-medium text-foreground">{latestResult.recommendation}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Emotional State Trends
          </CardTitle>
          <CardDescription>
            {role === 'caregiver'
              ? 'A limited wellness overview for caregiver support'
              : 'Recent distress trajectory from stored emotion logs'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="h-56 w-full">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [`${v}`, 'Distress']} />
                    <Line type="monotone" dataKey="distress" stroke="hsl(var(--primary))" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground">No trend points yet. Send a few check-in messages to populate the chart.</p>
              )}
            </div>
            <div className="rounded-lg border border-border p-4">
              <div className="mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-health-danger" />
                <span className="font-medium">Crisis Events</span>
              </div>
              {crisisEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground">No crisis events recorded.</p>
              ) : (
                <div className="space-y-3">
                  {crisisEvents.slice(0, 8).map((event) => (
                    <div key={event.id} className="flex flex-col gap-2 border-b border-border/60 pb-2 text-sm text-muted-foreground last:border-0 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        Patient {event.patient_id} · {(event.probability * 100).toFixed(0)}% · {event.action_taken}
                        {event.acknowledged_at && <span className="ml-2 text-xs text-health-success">Acknowledged</span>}
                      </div>
                      {isDoctor && !event.acknowledged_at && (
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={() => void onAckCrisis(event)}>
                            Acknowledge
                          </Button>
                          <Button size="sm" onClick={() => void onClearGate(event.patient_id)}>
                            Clear session gate
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
