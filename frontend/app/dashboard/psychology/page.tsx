'use client'

import { useEffect, useMemo, useState } from 'react'
import { MessageCircle, BarChart3, Heart, Zap, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useAuth } from '@/components/auth-context'
import { Input } from '@/components/ui/input'
import {
  endPsychologySession,
  getPsychologyTrends,
  listCrisisEvents,
  sendPsychologyMessage,
  startPsychologySession,
  type CrisisEvent,
  type PsychologyMessageResult,
  type TrendPoint,
} from '@/lib/psychology-api'

type ChatBubble = {
  role: 'patient' | 'assistant'
  content: string
}

export default function PsychologyPage() {
  const { user } = useAuth()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [chat, setChat] = useState<ChatBubble[]>([])
  const [latestResult, setLatestResult] = useState<PsychologyMessageResult | null>(null)
  const [trends, setTrends] = useState<TrendPoint[]>([])
  const [crisisEvents, setCrisisEvents] = useState<CrisisEvent[]>([])
  const [loading, setLoading] = useState(false)
  const role = user?.role
  const isPatient = role === 'patient'
  const isDoctor = role === 'doctor'
  const intro = isDoctor
    ? 'Review emotional trends and support signals for assigned patients.'
    : role === 'caregiver'
      ? 'Follow wellness status and support recommendations without exposing private therapy details.'
      : 'AI-powered emotional health tracking and therapy sessions.'
  const patientId = Number(user?.id || 0)

  useEffect(() => {
    if (!patientId) return
    let cancelled = false
    void startPsychologySession(patientId, 'en')
      .then((payload) => {
        if (!cancelled) setSessionId(payload.session_id)
      })
      .catch(() => {
        if (!cancelled) setSessionId(null)
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
    void listCrisisEvents(isDoctor ? undefined : patientId)
      .then((items) => {
        if (!cancelled) setCrisisEvents(items)
      })
      .catch(() => {
        if (!cancelled) setCrisisEvents([])
      })
    return () => {
      cancelled = true
    }
  }, [patientId, isDoctor])

  const stressPercent = useMemo(() => {
    if (!latestResult) return 25
    return Math.round(Math.max(0, Math.min(100, latestResult.distress_score * 100)))
  }, [latestResult])

  async function submitMessage() {
    if (!sessionId || !input.trim() || !patientId) return
    const patientText = input.trim()
    setInput('')
    setChat((old) => [...old, { role: 'patient', content: patientText }])
    setLoading(true)
    try {
      const result = await sendPsychologyMessage({ session_id: sessionId, patient_id: patientId, text: patientText })
      setLatestResult(result)
      setChat((old) => [...old, { role: 'assistant', content: result.reply }])
      const trendPayload = await getPsychologyTrends(patientId)
      setTrends(trendPayload.points)
      if (result.crisis_detected) {
        const events = await listCrisisEvents(isDoctor ? undefined : patientId)
        setCrisisEvents(events)
      }
    } finally {
      setLoading(false)
    }
  }

  async function closeSession() {
    if (!sessionId || !patientId) return
    await endPsychologySession(sessionId, patientId)
    setSessionId(null)
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Psychology & Mental Wellness</h1>
        <p className="text-muted-foreground mt-2">{intro}</p>
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
                <p className="text-lg font-bold">{latestResult?.mental_state ?? 'Neutral'}</p>
                <p className="text-xs text-muted-foreground">Current detected emotional state</p>
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
              <div className="text-3xl font-bold text-health-warning">{stressPercent}%</div>
              <div className="flex-1">
                <Progress value={stressPercent} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1">Distress score from multimodal fusion</p>
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
                  <Button size="icon" onClick={() => void submitMessage()} disabled={loading || !sessionId}>
                    <MessageCircle className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" onClick={() => void closeSession()} disabled={!sessionId}>
                    End
                  </Button>
                </div>
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
              : 'Weekly mood and stress patterns'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium">Distress trajectory (7 sessions)</span>
                <span className="text-sm text-muted-foreground">
                  {trends.length > 0 ? `${Math.round(trends[trends.length - 1]!.distress_score * 100)}/100` : 'No data'}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
                {(trends.length > 0 ? trends : [{ distress_score: 0.25 } as TrendPoint]).map((point, idx) => (
                  <div key={idx} className="flex flex-col items-center">
                    <div
                      className="w-full bg-health-warning rounded-sm"
                      style={{ height: `${Math.max(6, point.distress_score * 60)}px` }}
                    />
                    <p className="text-xs text-muted-foreground mt-1">S{idx + 1}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border p-4">
              <div className="mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-health-danger" />
                <span className="font-medium">Crisis Events</span>
              </div>
              {crisisEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground">No crisis events recorded.</p>
              ) : (
                <div className="space-y-2">
                  {crisisEvents.slice(0, 4).map((event) => (
                    <div key={event.id} className="text-sm text-muted-foreground">
                      Patient {event.patient_id} · {(event.probability * 100).toFixed(0)}% · {event.action_taken}
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
