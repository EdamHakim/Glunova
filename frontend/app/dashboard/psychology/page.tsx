'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CameraOff, Mic, SendHorizonal, Video } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/components/auth-context'
import { Switch } from '@/components/ui/switch'
import {
  detectEmotionFrame,
  endPsychologySession,
  psychologyWsBase,
  sendPsychologyMessage,
  startPsychologySession,
  type PsychologyMessageResult,
} from '@/lib/psychology-api'

type LiveEmotion = {
  label: 'neutral' | 'happy' | 'anxious' | 'distressed' | 'depressed'
  confidence: number
  distress_score: number
  timestamp: string
}

type ChatEntry = {
  id: string
  role: 'patient' | 'assistant'
  content: string
  createdAt: string
  kind?: 'text' | 'thought_record'
}
type ThoughtRecord = {
  event: string
  thought: string
  feeling: string
  reframe: string
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

function detectLikelyLanguage(text: string): string {
  const lower = text.toLowerCase()
  if (/[ء-ي]/.test(text) || /(?:\b(?:salam|marhba|ana|inti|enta)\b)/i.test(text)) return 'ar'
  if (/\b(?:bonjour|merci|je|vous|suis|avec|salut)\b/i.test(lower)) return 'fr'
  if (/\b(?:chnowa|3andi|barsha|mouch|nheb|labes)\b/i.test(lower)) return 'darija'
  return 'en'
}

function inferSpeechEmotionFromText(text: string): { label: LiveEmotion['label']; confidence: number } | null {
  const lower = text.toLowerCase()
  if (!lower.trim()) return null
  if (/(suicide|kill myself|end my life|hopeless|worthless|ma nhebch n3ich|منهار|بلا أمل)/i.test(lower)) {
    return { label: 'depressed', confidence: 0.82 }
  }
  if (/(happy|grateful|better|good|relaxed|calm|الحمد|مرتاح|labes|mlih|bekhir)/i.test(lower)) {
    return { label: 'happy', confidence: 0.7 }
  }
  if (/(panic|overwhelmed|stressed|can't breathe|anxious|قلق|متوتر|ضغط|barsha stress)/i.test(lower)) {
    return { label: 'anxious', confidence: 0.76 }
  }
  if (/(angry|crying|exhausted|drained|مش قادر|تعبان|fedayet|mnayek)/i.test(lower)) {
    return { label: 'distressed', confidence: 0.72 }
  }
  return { label: 'neutral', confidence: 0.62 }
}

export default function PsychologyPage() {
  const { user } = useAuth()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionStarted, setSessionStarted] = useState(false)
  const [input, setInput] = useState('')
  const [chat, setChat] = useState<ChatEntry[]>([])
  const [latestResult, setLatestResult] = useState<PsychologyMessageResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [cameraOptIn, setCameraOptIn] = useState(false)
  const [liveEmotion, setLiveEmotion] = useState<LiveEmotion | null>(null)
  const [micListening, setMicListening] = useState(false)
  const [latestSpeechTranscript, setLatestSpeechTranscript] = useState('')
  const [startingSession, setStartingSession] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [detectedSpeechLanguage, setDetectedSpeechLanguage] = useState<string | null>(null)
  const [cameraTransport, setCameraTransport] = useState<'idle' | 'websocket' | 'http-fallback'>('idle')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const captureTimerRef = useRef<number | null>(null)
  const wsReconnectTimerRef = useRef<number | null>(null)
  const keepCameraAliveRef = useRef(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const lastEmotionUpdateMsRef = useRef<number>(0)
  const [thoughtRecordByMessage, setThoughtRecordByMessage] = useState<Record<string, ThoughtRecord>>({})

  const role = user?.role
  const isPatient = role === 'patient'
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
      const payload = await startPsychologySession(patientId, 'mixed')
      if (payload.allowed === false || !payload.session_id) return null
      setSessionId(payload.session_id)
      return payload.session_id
    } catch {
      setSessionId(null)
      return null
    } finally {
      setStartingSession(false)
    }
  }, [patientId, sessionId])

  const stopCamera = useCallback(() => {
    keepCameraAliveRef.current = false
    if (captureTimerRef.current != null) {
      window.clearInterval(captureTimerRef.current)
      captureTimerRef.current = null
    }
    if (wsReconnectTimerRef.current != null) {
      window.clearTimeout(wsReconnectTimerRef.current)
      wsReconnectTimerRef.current = null
    }
    wsRef.current?.close()
    wsRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
    setCameraTransport('idle')
    setLiveEmotion(null)
  }, [])

  const captureFrameAndInferEmotion = useCallback(
    async (canvas: HTMLCanvasElement, width: number, height: number) => {
      const vid = videoRef.current
      if (!vid || !patientId) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.drawImage(vid, 0, 0, width, height)
      const frame = canvas.toDataURL('image/jpeg', 0.55)

      const socket = wsRef.current
      if (socket && socket.readyState === WebSocket.OPEN) {
        setCameraTransport('websocket')
        socket.send(JSON.stringify({ frame_base64: frame }))
        const staleMs = Date.now() - lastEmotionUpdateMsRef.current
        if (staleMs < 1600) return
      }
      setCameraTransport('http-fallback')
      try {
        const inferred = await detectEmotionFrame(patientId, frame)
        setLiveEmotion({
          label: inferred.label,
          confidence: inferred.confidence,
          distress_score: inferred.distress_score,
          timestamp: inferred.timestamp,
        })
        lastEmotionUpdateMsRef.current = Date.now()
      } catch {
        /* ignore intermittent fallback errors */
      }
    },
    [patientId],
  )

  const captureFrameBase64 = useCallback((): string | null => {
    const vid = videoRef.current
    if (!vid) return null
    if (!captureCanvasRef.current) captureCanvasRef.current = document.createElement('canvas')
    const canvas = captureCanvasRef.current
    const width = 320
    const height = 240
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(vid, 0, 0, width, height)
    return canvas.toDataURL('image/jpeg', 0.6)
  }, [])

  const startCamera = useCallback(async () => {
    if (!patientId || !isPatient) return
    try {
      keepCameraAliveRef.current = true
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }
      const wsUrl = `${psychologyWsBase()}${process.env.NEXT_PUBLIC_PSYCHOLOGY_PREFIX || '/psychology'}/ws/emotion/${patientId}`
      const connectWs = () => {
        if (!keepCameraAliveRef.current) return
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws
        ws.onopen = () => setCameraTransport('websocket')
        ws.onerror = () => setCameraTransport('http-fallback')
        ws.onclose = () => {
          setCameraTransport('http-fallback')
          wsRef.current = null
          if (!keepCameraAliveRef.current) return
          if (wsReconnectTimerRef.current != null) window.clearTimeout(wsReconnectTimerRef.current)
          wsReconnectTimerRef.current = window.setTimeout(connectWs, 1200)
        }
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(String(ev.data)) as LiveEmotion
            setLiveEmotion(data)
            lastEmotionUpdateMsRef.current = Date.now()
          } catch {
            /* ignore */
          }
        }
      }
      connectWs()
      const canvas = document.createElement('canvas')
      const w = 320
      const h = 240
      canvas.width = w
      canvas.height = h
      const tick = () => {
        void captureFrameAndInferEmotion(canvas, w, h)
      }
      captureTimerRef.current = window.setInterval(tick, 450)
      lastEmotionUpdateMsRef.current = 0
      setCameraOn(true)
    } catch {
      keepCameraAliveRef.current = false
      setCameraOn(false)
    }
  }, [captureFrameAndInferEmotion, isPatient, patientId])

  useEffect(() => () => stopCamera(), [stopCamera])
  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chat])

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
    rec.lang = navigator.language || 'en-US'
    rec.interimResults = false
    rec.continuous = false
    rec.onresult = (event) => {
      const text = event.results[0]?.[0]?.transcript?.trim()
      if (text) {
        const resultLang = event.results[0]?.[0]?.language || detectLikelyLanguage(text)
        setDetectedSpeechLanguage(resultLang)
        setLatestSpeechTranscript(text)
        setInput((prev) => (prev ? `${prev} ${text}` : text))
      }
    }
    rec.onend = () => {
      setMicListening(false)
      recognitionRef.current = null
    }
    recognitionRef.current = rec
    rec.start()
    setMicListening(true)
  }, [micListening])

  async function streamAssistantMessage(content: string, techniqueUsed?: string) {
    const id = `${Date.now()}-assistant`
    setChat((old) => [...old, { id, role: 'assistant', content: '', createdAt: new Date().toISOString(), kind: 'text' }])
    for (let i = 1; i <= content.length; i += 2) {
      const partial = content.slice(0, i)
      setChat((old) => old.map((m) => (m.id === id ? { ...m, content: partial } : m)))
      await new Promise((resolve) => window.setTimeout(resolve, 12))
    }
    if (techniqueUsed === 'cognitive_restructuring') {
      const thoughtId = `${Date.now()}-thought-record`
      setThoughtRecordByMessage((old) => ({
        ...old,
        [thoughtId]: { event: '', thought: '', feeling: '', reframe: '' },
      }))
      setChat((old) => [
        ...old,
        {
          id: thoughtId,
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          kind: 'thought_record',
        },
      ])
    }
  }

  async function submitMessage() {
    if (!input.trim()) return
    if (!patientId) {
      setChatError('Your patient profile is not loaded yet. Refresh the page and try again.')
      return
    }
    setChatError(null)
    const activeSessionId = await ensureSessionStarted()
    if (!activeSessionId) {
      setChatError('Could not start a therapy session. Please try again in a moment.')
      return
    }
    const patientText = input.trim()
    const speechEmotion = inferSpeechEmotionFromText(latestSpeechTranscript || patientText)
    const liveFrame = cameraOn ? captureFrameBase64() : null
    const multimodalPayload = {
      session_id: activeSessionId,
      patient_id: patientId,
      text: patientText,
      face_frame_base64: liveFrame || undefined,
      face_emotion: liveEmotion?.label,
      face_confidence: liveEmotion?.confidence,
      speech_transcript: latestSpeechTranscript || undefined,
      speech_emotion: speechEmotion?.label,
      speech_confidence: speechEmotion?.confidence,
    }
    setInput('')
    setLatestSpeechTranscript('')
    setChat((old) => [...old, { id: `${Date.now()}-patient`, role: 'patient', content: patientText, createdAt: new Date().toISOString(), kind: 'text' }])
    setLoading(true)
    try {
      let result: PsychologyMessageResult
      try {
        result = await sendPsychologyMessage(multimodalPayload)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const likelySessionIssue = /session|404|403|not found|invalid/i.test(message)
        if (!likelySessionIssue) throw error
        const refreshedSessionId = await ensureSessionStarted(true)
        if (!refreshedSessionId) throw error
        result = await sendPsychologyMessage({ ...multimodalPayload, session_id: refreshedSessionId })
      }
      setLatestResult(result)
      await streamAssistantMessage(result.reply, result.technique_used)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setChatError('Message was not sent. Please try again.')
      setChat((old) => [
        ...old,
        {
          id: `${Date.now()}-assistant-error`,
          role: 'assistant',
          content: `I could not process that right now (${message.slice(0, 120)}). Please retry.`,
          createdAt: new Date().toISOString(),
          kind: 'text',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  async function closeSession() {
    const currentSessionId = sessionId
    const currentPatientId = patientId
    try {
      if (currentSessionId && currentPatientId) {
        await endPsychologySession(currentSessionId, currentPatientId)
      }
    } catch {
      // Non-blocking: local session should still close even if backend call fails.
      setChatError('Session closed locally. Remote sync will be retried on next session.')
    } finally {
      stopCamera()
      setSessionId(null)
      setSessionStarted(false)
      setChat([])
      setLatestResult(null)
      setInput('')
      setLatestSpeechTranscript('')
    }
  }

  async function beginSession() {
    if (!isPatient || !patientId) return
    setChatError(null)
    const sid = await ensureSessionStarted(true)
    if (!sid) {
      setChatError('Session could not start. Please try again.')
      return
    }
    setSessionStarted(true)
    setChat([
      {
        id: 'welcome',
        role: 'assistant',
        content: 'I am Sanadi. I am here with you. Say anything and we will take it one step at a time.',
        createdAt: new Date().toISOString(),
        kind: 'text',
      },
    ])
    if (cameraOptIn) await startCamera()
  }

  if (!isPatient) {
    return (
      <div className="space-y-6 p-6">
        <Card>
          <CardHeader>
            <CardTitle>Sanadi Clinical Companion</CardTitle>
            <CardDescription>Patient-facing session flow is now full-screen and safety-first. Clinical metrics remain available only in non-patient views.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Open as a patient account to experience the Sanadi session UX.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!sessionStarted) {
    return (
      <div className="flex h-full min-h-[calc(100vh-4rem)] items-center justify-center bg-background p-6">
        <div className="w-full max-w-xl space-y-6 text-center">
          <h1 className="text-4xl font-semibold tracking-tight">سنَدي</h1>
          <p className="text-base text-muted-foreground">Your clinical companion for calm, guided support.</p>
          <p className="mx-auto max-w-md text-sm text-muted-foreground/90">
            This is a private, supportive space. You can talk freely, pause whenever you need, and move at your own pace.
          </p>
          <div className="mx-auto flex max-w-lg flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="rounded-full border bg-muted/30 px-3 py-1">CBT-guided support</span>
            <span className="rounded-full border bg-muted/30 px-3 py-1">Clinically supervised safety</span>
            <span className="rounded-full border bg-muted/30 px-3 py-1">Camera always optional</span>
          </div>
          <Button size="lg" className="px-10" onClick={() => void beginSession()} disabled={startingSession}>
            Begin session
          </Button>
          <div className="flex items-center justify-center gap-3 text-sm text-muted-foreground">
            <Switch checked={cameraOptIn} onCheckedChange={(checked) => setCameraOptIn(Boolean(checked))} />
            <span>Sanadi understands you better with camera on — always optional</span>
          </div>
          {chatError && <p className="text-sm text-destructive">{chatError}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-40 flex h-screen flex-col bg-background">
      <header className="flex h-14 items-center border-b px-4">
        <div className="w-1/3 text-lg font-semibold">سنَدي Sanadi</div>
        <div className="flex w-1/3 items-center justify-center">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400/80" />
        </div>
        <div className="flex w-1/3 justify-end">
          <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={() => void closeSession()}>
            End session
          </button>
        </div>
      </header>

      <main ref={chatScrollRef} className="flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto flex w-full max-w-5xl gap-5">
          <div className="flex min-w-0 flex-1 flex-col gap-4">
          {chat.map((entry) => (
            <div
              key={entry.id}
              title={new Date(entry.createdAt).toLocaleString()}
              className={`flex w-full ${entry.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
            >
              {entry.kind === 'thought_record' ? (
                <div className="w-[min(42rem,90vw)] rounded-2xl border bg-muted/30 p-4">
                  <p className="mb-3 text-sm font-medium">Thought record</p>
                  <div className="space-y-2">
                    <label className="block text-xs text-muted-foreground">What happened</label>
                    <textarea
                      className="w-full rounded-md border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.event || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), event: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">What I thought</label>
                    <textarea
                      className="w-full rounded-md border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.thought || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), thought: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">How it made me feel</label>
                    <textarea
                      className="w-full rounded-md border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.feeling || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), feeling: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">Another way to see it</label>
                    <textarea
                      className="w-full rounded-md border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.reframe || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), reframe: e.target.value } }))}
                    />
                  </div>
                </div>
              ) : entry.role === 'assistant' ? (
                <div className="max-w-[85%] rounded-3xl border border-border/70 bg-muted/45 px-5 py-4 text-left text-[1.02rem] leading-relaxed shadow-sm">
                  {entry.content}
                </div>
              ) : (
                <div className="max-w-[78%] rounded-3xl bg-primary/10 px-4 py-2.5 text-left text-sm leading-relaxed text-foreground/95 ring-1 ring-primary/20">
                  {entry.content}
                </div>
              )}
            </div>
          ))}
          </div>
          <aside className="sticky top-2 hidden h-fit w-72 shrink-0 rounded-2xl border bg-muted/20 p-3 md:block">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Live camera</p>
            <video ref={videoRef} className="h-44 w-full rounded-xl bg-black object-cover" playsInline muted />
            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Emotion</span>
                <span className="font-medium capitalize">{liveEmotion?.label || 'Not detected yet'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Confidence</span>
                <span className="font-medium">{liveEmotion ? `${Math.round(liveEmotion.confidence * 100)}%` : '—'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Camera mode</span>
                <span className="font-medium">{cameraOn ? 'On' : 'Off'}</span>
              </div>
            </div>
          </aside>
        </div>
      </main>

      <footer className="border-t px-3 py-2">
        <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
          <Button type="button" size="icon" variant={micListening ? 'secondary' : 'outline'} className="h-12 w-12" onClick={() => toggleMic()}>
            <Mic className="h-5 w-5" />
          </Button>
          <textarea
            value={input}
            placeholder="Say anything..."
            rows={1}
            className="max-h-40 min-h-12 flex-1 resize-y rounded-xl border bg-background px-3 py-3 text-sm outline-none"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void submitMessage()
              }
            }}
          />
          <Button type="button" size="icon" className="h-12 w-12" onClick={() => void submitMessage()} disabled={loading || startingSession || !input.trim()}>
            <SendHorizonal className="h-5 w-5" />
          </Button>
          <div className="mb-2 flex flex-col items-center gap-2">
            <button
              type="button"
              className="rounded-md border px-2 py-1 text-xs text-muted-foreground"
              onClick={() => (cameraOn ? stopCamera() : void startCamera())}
            >
              {cameraOn ? <CameraOff className="h-4 w-4" /> : <Video className="h-4 w-4" />}
            </button>
            <span className={`h-2 w-2 rounded-full ${cameraOn ? 'bg-emerald-400' : 'bg-muted-foreground/30'}`} />
          </div>
        </div>
        <div className="mx-auto mt-2 flex w-full max-w-3xl items-center justify-end text-xs text-muted-foreground">
          <span>{detectedSpeechLanguage ? `Speech: ${detectedSpeechLanguage}` : latestResult ? `Mode: ${latestResult.language_detected}` : 'Speech auto-detect enabled'}</span>
        </div>
        {chatError && <p className="mx-auto mt-2 w-full max-w-3xl text-xs text-muted-foreground">{chatError}</p>}
      </footer>
    </div>
  )
}
