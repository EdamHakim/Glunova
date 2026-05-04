'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Noto_Sans_Arabic } from 'next/font/google'
import {
  CameraOff,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Headphones,
  Mic,
  SendHorizonal,
  Sparkles,
  Video,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { useAuth } from '@/components/auth-context'
import { Switch } from '@/components/ui/switch'
import {
  detectEmotionFrame,
  endPsychologySession,
  psychologyWsBase,
  sendPsychologyMessage,
  startPsychologySession,
  synthesizePsychologyVoice,
  transcribePsychologyVoice,
  type PsychologyMessageResult,
} from '@/lib/psychology-api'
import type { AvatarPhase } from '@/components/psychology/sanadi-avatar'
import {
  SanadiTalkingHead,
  type SanadiTalkingHeadHandle,
  type PsychologyTtsLang as SanadiPsychologyTtsLang,
} from '@/components/psychology/sanadi-talkinghead'
import { SanadiMoodRing } from '@/components/psychology/sanadi-mood-ring'
import { SanadiVoiceWaveform, type WaveformSpeaker } from '@/components/psychology/sanadi-waveform'
import { cn } from '@/lib/utils'

const notoSansArabic = Noto_Sans_Arabic({
  subsets: ['arabic'],
  weight: ['400', '500', '600'],
  display: 'swap',
})

/** Matches FastAPI SessionStartRequest.preferred_language. */
type PreferredSessionLang = 'mixed' | 'en' | 'fr' | 'ar'

const SANADI_PREF_LANG_KEY = 'sanadi_pref_lang'


function coercePreferredLang(raw: string | null): PreferredSessionLang {
  if (raw === 'en' || raw === 'fr' || raw === 'ar' || raw === 'mixed') return raw
  return 'mixed'
}

type LiveEmotion = {
  label: 'neutral' | 'happy' | 'anxious' | 'distressed' | 'depressed'
  confidence: number
  distress_score: number
  timestamp: string
}

function pct01(n: number | undefined): string {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '—'
  return `${Math.round(Math.max(0, Math.min(1, n)) * 100)}%`
}

/** Client-side snapshots sent with last therapy message (+ speech/STT/audio flags). */
type RecognitionSentHints = {
  face: { label: string; confidence: number } | null
  speech: { label: string; confidence: number } | null
  text: { label: string; confidence: number } | null
  transcriptSnippet: string | null
  speechAudioIncluded: boolean
  speechAudioBase64Chars: number | null
}

function clipSnippet(s: string | null | undefined, max = 140): string | null {
  const t = (s ?? '').trim()
  if (!t) return null
  if (t.length <= max) return t
  return `${t.slice(0, Math.max(0, max - 1))}…`
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

function LanguagePicker({
  value,
  disabled,
  onChange,
}: {
  value: PreferredSessionLang
  disabled?: boolean
  onChange: (next: PreferredSessionLang) => void
}) {
  const opts: { id: PreferredSessionLang; label: string }[] = [
    { id: 'mixed', label: 'Auto' },
    { id: 'en', label: 'EN' },
    { id: 'fr', label: 'FR' },
    { id: 'ar', label: 'AR' },
  ]
  return (
    <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Session language">
      {opts.map((o) => (
        <Button
          key={o.id}
          type="button"
          size="sm"
          variant={value === o.id ? 'secondary' : 'outline'}
          className="h-8 min-w-[2.5rem] rounded-full px-2 text-xs shadow-sm"
          aria-pressed={value === o.id}
          disabled={disabled}
          onClick={() => onChange(o.id)}
        >
          {o.label}
        </Button>
      ))}
    </div>
  )
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
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const captureTimerRef = useRef<number | null>(null)
  const wsReconnectTimerRef = useRef<number | null>(null)
  const keepCameraAliveRef = useRef(false)
  const dictationRecorderRef = useRef<MediaRecorder | null>(null)
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const lastEmotionUpdateMsRef = useRef<number>(0)
  const [thoughtRecordByMessage, setThoughtRecordByMessage] = useState<Record<string, ThoughtRecord>>({})
  const [voiceModeActive, setVoiceModeActive] = useState(false)
  const [avatarPhase, setAvatarPhase] = useState<AvatarPhase>('idle')
  const [voiceRecording, setVoiceRecording] = useState(false)

  const voiceRecorderRef = useRef<MediaRecorder | null>(null)
  const discardVoiceRecordingRef = useRef(false)
  const voiceStreamRef = useRef<MediaStream | null>(null)
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)
  const ttsObjectUrlRef = useRef<string | null>(null)
  const latestResultLangRef = useRef<PsychologyMessageResult['language_detected'] | null>(null)
  const voiceAnalyserRef = useRef<AnalyserNode | null>(null)
  const recordingAudioCtxRef = useRef<AudioContext | null>(null)
  const ttsAudioCtxRef = useRef<AudioContext | null>(null)
  const talkingHeadRef = useRef<SanadiTalkingHeadHandle | null>(null)

  const [railCollapsed, setRailCollapsed] = useState(true)
  const [visitOrdinal, setVisitOrdinal] = useState(1)
  const [preferredSessionLang, setPreferredSessionLang] = useState<PreferredSessionLang>('mixed')
  const [cameraPanelOpen, setCameraPanelOpen] = useState(false)
  const [recognitionDebugOpen, setRecognitionDebugOpen] = useState(false)
  const [lastRecognitionSentHints, setLastRecognitionSentHints] = useState<RecognitionSentHints | null>(null)

  const role = user?.role
  const isPatient = role === 'patient'
  const displayEmotion = liveEmotion
    ? { label: liveEmotion.label, confidence: liveEmotion.confidence }
    : latestResult?.fusion
      ? { label: latestResult.fusion.label, confidence: latestResult.fusion.confidence }
      : latestResult
        ? { label: latestResult.emotion, confidence: 0.65 }
      : null
  const waveSpeaker: WaveformSpeaker = useMemo(() => {
    if (!voiceModeActive) return 'idle'
    if (voiceRecording) return 'patient'
    if (avatarPhase === 'speaking') return 'assistant'
    return 'idle'
  }, [voiceModeActive, voiceRecording, avatarPhase])

  const voicePhaseLine = useMemo(() => {
    if (avatarPhase === 'listening') return 'Sanadi is listening'
    if (avatarPhase === 'thinking') return 'Sanadi is thinking'
    if (avatarPhase === 'speaking') return 'Sanadi is speaking'
    return 'Ready when you are'
  }, [avatarPhase])

  const recognitionDebugText = useMemo(() => {
    const speechInFusion = !!latestResult?.fusion?.modalities_used?.includes('speech')

    const lines: string[] = []
    lines.push('━━ Face · live WS / periodic frame ━━')
    if (liveEmotion) {
      lines.push(`label: ${liveEmotion.label}`)
      lines.push(`confidence: ${pct01(liveEmotion.confidence)} (raw ${liveEmotion.confidence.toFixed(3)})`)
      lines.push(`distress_score: ${liveEmotion.distress_score?.toFixed(3) ?? '—'}`)
      lines.push(`timestamp: ${liveEmotion.timestamp}`)
    } else lines.push('(none — open camera preview or rely on WS + periodic frame inference)')
    lines.push('')
    lines.push('━━ Speech · last client/STT payload (voice + dictation) ━━')
    if (!lastRecognitionSentHints) lines.push('(no message sent yet in this session)')
    else {
      const h = lastRecognitionSentHints
      lines.push(
        `speech_transcript (STT excerpt): ${h.transcriptSnippet ?? '(not sent — typed-only turns omit transcript unless mic dictation added one)'}`,
      )
      if (h.speechAudioIncluded) {
        const ch = h.speechAudioBase64Chars
        const approxBytes = typeof ch === 'number' && ch > 0 ? Math.floor((ch * 3) / 4) : null
        lines.push(`speech_audio: yes${approxBytes != null ? ` (~${approxBytes} bytes from base64)` : ''}`)
      } else lines.push(`speech_audio: no (Groq/STT transcript only)`)
      lines.push(`emotion_hint from transcript heuristic: ${h.speech ? `${h.speech.label} · ${pct01(h.speech.confidence)}` : '(none — heuristic could not classify)'}`)
      lines.push(
        `(Voice mode sends transcript + speech_audio_base64 so the server can run audio emotion then fuse; typed chat sends text hints only unless you dictated text.)`,
      )
      lines.push('')
      lines.push('━━ Other modality hints bundled on same request ━━')
      lines.push(`face hint → ${h.face ? `${h.face.label} · conf ${pct01(h.face.confidence)}` : '— (no live face cached on payload)'}`)
      lines.push(
        `text (message body) heuristic → ${h.text ? `${h.text.label} · conf ${pct01(h.text.confidence)}` : '—'} (server still runs full text emotion model)`,
      )
    }
    lines.push('')
    lines.push('━━ Server fusion · last therapy response ━━')
    if (!latestResult?.fusion) lines.push('(no assistant reply yet — fusion appears after each exchange)')
    else {
      const f = latestResult.fusion
      lines.push(`fusion.label: ${f.label}`)
      lines.push(`fusion.confidence: ${pct01(f.confidence)} (raw ${f.confidence.toFixed(3)})`)
      lines.push(`distress_score: ${f.distress_score}`)
      lines.push(`stress_level: ${f.stress_level}`)
      lines.push(`sentiment_score (text-based on server): ${f.sentiment_score}`)
      lines.push(`modalities_used: ${f.modalities_used.join(', ')}`)
      lines.push(`speech listed in modalities_used: ${speechInFusion ? 'yes' : 'no'} (needs STT transcript and/or speech audio)`)
      lines.push(`response.emotion (top-level): ${latestResult.emotion}`)
    }
    return lines.join('\n')
  }, [liveEmotion, lastRecognitionSentHints, latestResult])
  const sessionDir = preferredSessionLang === 'ar' ? 'rtl' : 'ltr'
  const sessionLangAttr =
    preferredSessionLang === 'fr' ? 'fr' : preferredSessionLang === 'ar' ? 'ar' : preferredSessionLang === 'en' ? 'en' : 'en'

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
      const payload = await startPsychologySession(patientId, preferredSessionLang)
      if (payload.allowed === false || !payload.session_id) return null
      setSessionId(payload.session_id)
      return payload.session_id
    } catch {
      setSessionId(null)
      return null
    } finally {
      setStartingSession(false)
    }
  }, [patientId, sessionId, preferredSessionLang])

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
        socket.send(JSON.stringify({ frame_base64: frame }))
        const staleMs = Date.now() - lastEmotionUpdateMsRef.current
        if (staleMs < 1600) return
      }
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
        ws.onclose = () => {
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

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      setPreferredSessionLang(coercePreferredLang(sessionStorage.getItem(SANADI_PREF_LANG_KEY)))
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      sessionStorage.setItem(SANADI_PREF_LANG_KEY, preferredSessionLang)
    } catch {
      /* ignore */
    }
  }, [preferredSessionLang])

  useEffect(() => {
    if (!liveEmotion) return
    // eslint-disable-next-line no-console -- intentional debug for recognition QA
    console.log('[Sanadi] live face emotion (WS / frame)', {
      label: liveEmotion.label,
      confidence: liveEmotion.confidence,
      confidencePct: pct01(liveEmotion.confidence),
      distress_score: liveEmotion.distress_score,
      timestamp: liveEmotion.timestamp,
    })
  }, [liveEmotion])

  useEffect(() => {
    if (!latestResult) return
    const f = latestResult.fusion
    // eslint-disable-next-line no-console -- intentional debug for recognition QA
    console.log('[Sanadi] last therapy fusion + modalities', {
      topLevelEmotion: latestResult.emotion,
      fusion: f
        ? {
            label: f.label,
            confidence: f.confidence,
            confidencePct: pct01(f.confidence),
            distress_score: f.distress_score,
            stress_level: f.stress_level,
            sentiment_score: f.sentiment_score,
            modalities_used: f.modalities_used,
            speechModalityIncluded: !!(f.modalities_used?.includes && f.modalities_used.includes('speech')),
          }
        : null,
    })
  }, [latestResult])

  const toggleMic = useCallback(() => {
    if (micListening) {
      dictationRecorderRef.current?.stop()
      return
    }
    void (async () => {
      if (!navigator.mediaDevices?.getUserMedia) return
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        })
        const mime = pickVoiceRecorderMime()
        const chunks: BlobPart[] = []
        const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
        dictationRecorderRef.current = recorder
        recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
        recorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop())
          dictationRecorderRef.current = null
          setMicListening(false)
          const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (blob.size < 400) return
          void (async () => {
            try {
              const fd = new FormData()
              const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
              fd.append('audio', blob, `dictation.${ext}`)
              const lang = preferredSessionLang !== 'mixed' ? preferredSessionLang : null
              if (lang) fd.append('language_hint', lang)
              const tr = await transcribePsychologyVoice(fd)
              const text = tr.text.trim()
              if (text) {
                setLatestSpeechTranscript(text)
                setInput((prev) => (prev ? `${prev} ${text}` : text))
              }
            } catch {
              /* transcription failed — user can type manually */
            }
          })()
        }
        recorder.start(240)
        setMicListening(true)
      } catch {
        /* microphone permission denied */
      }
    })()
  }, [micListening, preferredSessionLang])

  const onTalkingHeadAnalyserNode = useCallback((node: AnalyserNode | null) => {
    voiceAnalyserRef.current = node
  }, [])

  const stopAssistantTts = useCallback(() => {
    talkingHeadRef.current?.interruptSpeech()
    const a = ttsAudioRef.current
    if (a) {
      a.pause()
      a.src = ''
      ttsAudioRef.current = null
    }
    const u = ttsObjectUrlRef.current
    if (u) {
      URL.revokeObjectURL(u)
      ttsObjectUrlRef.current = null
    }
    void ttsAudioCtxRef.current?.close()
    ttsAudioCtxRef.current = null
    voiceAnalyserRef.current = null
  }, [])


  const speakAssistantReply = useCallback(
    async (reply: string, lang: PsychologyMessageResult['language_detected']) => {
      stopAssistantTts()
      setAvatarPhase('speaking')
      try {
        void recordingAudioCtxRef.current?.close()
        recordingAudioCtxRef.current = null
        voiceAnalyserRef.current = null
        const blob = await synthesizePsychologyVoice({ text: reply, language: lang })

        if (voiceModeActive) {
          const deadline = Date.now() + 4000
          while (Date.now() < deadline && !talkingHeadRef.current?.isAvatarReady?.()) {
            await new Promise((r) => setTimeout(r, 90))
          }
        }

        const th = talkingHeadRef.current
        if (voiceModeActive && th?.isAvatarReady?.()) {
          const played = await th.speakFromServiceTts(
            blob,
            reply,
            lang as SanadiPsychologyTtsLang,
            () => setAvatarPhase('idle'),
          )
          if (played) return
        }

        const url = URL.createObjectURL(blob)
        ttsObjectUrlRef.current = url
        const audio = new Audio(url)
        ttsAudioRef.current = audio
        audio.onended = () => {
          stopAssistantTts()
          setAvatarPhase('idle')
        }
        audio.onerror = () => {
          stopAssistantTts()
          setAvatarPhase('idle')
        }
        try {
          const AC = typeof window !== 'undefined'
            ? window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
            : null
          if (AC) {
            const ctx = new AC()
            await ctx.resume().catch(() => {})
            ttsAudioCtxRef.current = ctx
            const analyser = ctx.createAnalyser()
            analyser.fftSize = 256
            const mes = ctx.createMediaElementSource(audio)
            mes.connect(analyser)
            analyser.connect(ctx.destination)
            voiceAnalyserRef.current = analyser
          }
        } catch {
          /* Web Audio optional; element output still works */
        }
        await audio.play()
      } catch {
        stopAssistantTts()
        setAvatarPhase('idle')
      }
    },
    [stopAssistantTts, voiceModeActive],
  )

  useEffect(() => {
    return () => {
      stopAssistantTts()
      dictationRecorderRef.current?.stop()
      voiceRecorderRef.current?.stop()
      voiceStreamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [stopAssistantTts])

  async function blobToSpeechAudioBase64(blob: Blob): Promise<string | undefined> {
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const fr = new FileReader()
        fr.onloadend = () => resolve(String(fr.result ?? ''))
        fr.onerror = () => reject(new Error('read_failed'))
        fr.readAsDataURL(blob)
      })
      const raw = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl
      return raw || undefined
    } catch {
      return undefined
    }
  }

  function pickVoiceRecorderMime(): string | undefined {
    if (typeof MediaRecorder === 'undefined') return undefined
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    for (const c of candidates) {
      if (MediaRecorder.isTypeSupported(c)) return c
    }
    return undefined
  }

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

  async function appendAssistantAssistantContent(result: PsychologyMessageResult, assistantBehavior: 'stream' | 'voice') {
    if (assistantBehavior === 'voice') {
      const id = `${Date.now()}-assistant`
      setChat((old) => [
        ...old,
        { id, role: 'assistant', content: result.reply, createdAt: new Date().toISOString(), kind: 'text' },
      ])
      if (result.technique_used === 'cognitive_restructuring') {
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
      void speakAssistantReply(result.reply, result.language_detected)
      return
    }
    await streamAssistantMessage(result.reply, result.technique_used)
  }

  async function sendTherapyExchange(args: {
    patientText: string
    speechTranscript?: string
    speechAudioBase64?: string
    assistantUi: 'stream' | 'voice'
    clearTypingDraft?: boolean
  }) {
    const patientText = args.patientText.trim()
    if (!patientText) return
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
    const transcript = (args.speechTranscript ?? '').trim()
    const speechSource = transcript || patientText
    const speechEmotion = inferSpeechEmotionFromText(speechSource)
    const liveFrame = cameraOn ? captureFrameBase64() : null
    const multimodalPayload = {
      session_id: activeSessionId,
      patient_id: patientId,
      text: patientText,
      face_frame_base64: liveFrame || undefined,
      face_emotion: liveEmotion?.label,
      face_confidence: liveEmotion?.confidence,
      speech_transcript: transcript || undefined,
      speech_emotion: speechEmotion?.label,
      speech_confidence: speechEmotion?.confidence,
      ...(args.speechAudioBase64 ? { speech_audio_base64: args.speechAudioBase64 } : {}),
    }
    const textHeuristicEmotion = inferSpeechEmotionFromText(patientText)
    setLastRecognitionSentHints({
      face:
        typeof liveEmotion?.label === 'string' && typeof liveEmotion.confidence === 'number'
          ? { label: liveEmotion.label, confidence: liveEmotion.confidence }
          : null,
      speech:
        speechEmotion && typeof speechEmotion.confidence === 'number'
          ? { label: speechEmotion.label, confidence: speechEmotion.confidence }
          : null,
      text:
        textHeuristicEmotion && typeof textHeuristicEmotion.confidence === 'number'
          ? { label: textHeuristicEmotion.label, confidence: textHeuristicEmotion.confidence }
          : null,
      transcriptSnippet: clipSnippet(transcript),
      speechAudioIncluded: Boolean(args.speechAudioBase64),
      speechAudioBase64Chars: args.speechAudioBase64?.length ?? null,
    })
    if (args.clearTypingDraft) {
      setInput('')
      setLatestSpeechTranscript('')
    }
    if (args.assistantUi === 'voice') {
      setAvatarPhase('thinking')
    }
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
      setLiveEmotion((prev) => ({
        label: result.fusion?.label ?? result.emotion,
        confidence: result.fusion?.confidence ?? prev?.confidence ?? 0.65,
        distress_score: result.fusion?.distress_score ?? result.distress_score,
        timestamp: new Date().toISOString(),
      }))
      await appendAssistantAssistantContent(result, args.assistantUi === 'voice' ? 'voice' : 'stream')
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setChatError(args.assistantUi === 'voice' ? 'Voice reply was not delivered. Retry or disable Voice mode.' : 'Message was not sent. Please try again.')
      if (args.assistantUi === 'voice') setAvatarPhase('idle')
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
      if (args.assistantUi === 'voice') {
        // Speaking state is handled by audio pipeline; revert if no speech queued (handled in speak*)
      }
    }
  }

  async function submitMessage() {
    if (!input.trim() || voiceRecording) return
    await sendTherapyExchange({
      patientText: input.trim(),
      speechTranscript: latestSpeechTranscript || undefined,
      assistantUi: voiceModeActive ? 'voice' : 'stream',
      clearTypingDraft: true,
    })
  }

  useEffect(() => {
    latestResultLangRef.current = latestResult?.language_detected ?? null
  }, [latestResult?.language_detected])

  useEffect(() => {
    if (!voiceModeActive) {
      discardVoiceRecordingRef.current = true
      stopAssistantTts()
      if (voiceRecorderRef.current && voiceRecorderRef.current.state !== 'inactive') {
        voiceRecorderRef.current.stop()
      }
      voiceStreamRef.current?.getTracks().forEach((t) => t.stop())
      voiceStreamRef.current = null
      setVoiceRecording(false)
      setAvatarPhase('idle')
    }
  }, [voiceModeActive, stopAssistantTts])

  const startVoiceRecordingTurn = useCallback(async () => {
    discardVoiceRecordingRef.current = false
    stopAssistantTts()
    if (!patientId || !voiceModeActive) return
    if (!navigator.mediaDevices?.getUserMedia) {
      setChatError('Microphone is not available in this browser.')
      return
    }
    const existing = voiceRecorderRef.current
    if (existing && existing.state !== 'inactive') return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      })
      voiceStreamRef.current = stream
      void recordingAudioCtxRef.current?.close()
      recordingAudioCtxRef.current = null
      voiceAnalyserRef.current = null
      try {
        const AC =
          typeof window !== 'undefined'
            ? window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
            : null
        if (AC) {
          const ctx = new AC()
          await ctx.resume().catch(() => {})
          recordingAudioCtxRef.current = ctx
          const analyser = ctx.createAnalyser()
          analyser.fftSize = 256
          const src = ctx.createMediaStreamSource(stream)
          src.connect(analyser)
          voiceAnalyserRef.current = analyser
        }
      } catch {
        /* optional waveform */
      }
      const mime = pickVoiceRecorderMime()
      const chunks: BlobPart[] = []
      const recorder =
        mime && typeof MediaRecorder !== 'undefined' ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      voiceRecorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        void recordingAudioCtxRef.current?.close()
        recordingAudioCtxRef.current = null
        voiceAnalyserRef.current = null
        voiceStreamRef.current = null
        voiceRecorderRef.current = null
        const aborted = discardVoiceRecordingRef.current
        discardVoiceRecordingRef.current = false
        void (async () => {
          if (aborted) {
            setVoiceRecording(false)
            setAvatarPhase('idle')
            return
          }
          const blob = new Blob(chunks, { type: recorder.mimeType || mime || 'audio/webm' })
          setVoiceRecording(false)
          if (blob.size < 400) {
            setAvatarPhase('idle')
            setChatError('That clip was too short. Tap Speak again.')
            return
          }
          setAvatarPhase('thinking')
          try {
            const fd = new FormData()
            const typ = blob.type || ''
            const ext = typ.includes('mp4') || typ.includes('m4a') ? 'mp4' : typ.includes('webm') ? 'webm' : 'webm'
            fd.append('audio', blob, `recording.${ext}`)
            const hintLang = latestResultLangRef.current
            const explicitPref = preferredSessionLang !== 'mixed' ? preferredSessionLang : null
            const fromTurn = hintLang && hintLang !== 'mixed' ? (hintLang === 'darija' ? 'darija' : hintLang) : null
            const sttHint = explicitPref || fromTurn
            if (sttHint) {
              fd.append('language_hint', sttHint === 'darija' ? 'darija' : sttHint)
            }
            const tr = await transcribePsychologyVoice(fd)
            const trimmed = tr.text.trim()
            if (!trimmed) {
              setAvatarPhase('idle')
              setChatError('No speech detected — try speaking a little longer.')
              return
            }
            const b64 = await blobToSpeechAudioBase64(blob)
            await sendTherapyExchange({
              patientText: trimmed,
              speechTranscript: trimmed,
              speechAudioBase64: b64,
              assistantUi: 'voice',
              clearTypingDraft: false,
            })
          } catch {
            setChatError('Voice transcription failed (check STT/API). Retry or turn off Voice mode.')
            setAvatarPhase('idle')
          }
        })()
      }
      recorder.start(240)
      setVoiceRecording(true)
      setAvatarPhase('listening')
    } catch {
      setChatError('Microphone permission is required for Voice mode.')
      setAvatarPhase('idle')
    }
  }, [patientId, preferredSessionLang, voiceModeActive, stopAssistantTts])

  const stopVoiceRecordingTurn = useCallback(() => {
    const rec = voiceRecorderRef.current
    if (!rec || rec.state === 'inactive') return
    rec.stop()
  }, [])

  const abandonVoiceRecordingTurn = useCallback(() => {
    discardVoiceRecordingRef.current = true
    const rec = voiceRecorderRef.current
    if (rec && rec.state !== 'inactive') {
      rec.stop()
    }
  }, [])

  useEffect(() => {
    if (!sessionStarted) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && voiceRecording) {
        abandonVoiceRecordingTurn()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sessionStarted, voiceRecording, abandonVoiceRecordingTurn])

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
      stopAssistantTts()
      dictationRecorderRef.current?.stop()
      void recordingAudioCtxRef.current?.close()
      recordingAudioCtxRef.current = null
      voiceAnalyserRef.current = null
      setVoiceModeActive(false)
      setAvatarPhase('idle')
      setVoiceRecording(false)
      setSessionId(null)
      setSessionStarted(false)
      setChat([])
      setLatestResult(null)
      setLastRecognitionSentHints(null)
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
    try {
      const raw = typeof window !== 'undefined' ? window.sessionStorage.getItem('sanadi_session_visit_index') : null
      const parsed = raw ? Number.parseInt(raw, 10) : 0
      const next = Number.isFinite(parsed) && parsed >= 0 ? parsed + 1 : 1
      if (typeof window !== 'undefined') window.sessionStorage.setItem('sanadi_session_visit_index', String(next))
      setVisitOrdinal(next)
    } catch {
      setVisitOrdinal(1)
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
      <div
        lang={sessionLangAttr}
        dir={sessionDir}
        className={cn(
          'flex h-full min-h-[calc(100vh-4rem)] items-center justify-center bg-[color:var(--sanadi-surface-warm)] p-6',
          preferredSessionLang === 'ar' && notoSansArabic.className,
        )}
      >
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
          <div className="mx-auto flex max-w-md flex-col items-center gap-2">
            <p className="text-xs font-medium text-muted-foreground">Language</p>
            <LanguagePicker value={preferredSessionLang} onChange={setPreferredSessionLang} />
            <p className="text-[0.7rem] leading-snug text-muted-foreground">
              Choose before you begin. Your selection applies to this session and cannot be changed until you end it.
            </p>
          </div>
          <Button size="lg" className="px-10" onClick={() => void beginSession()} disabled={startingSession}>
            Begin session
          </Button>
          <div className="flex items-center justify-center gap-3 text-sm text-muted-foreground">
            <span>Sanadi understands you better with camera on — always optional</span>
          </div>
          {chatError && <p className="text-sm text-destructive">{chatError}</p>}
        </div>
      </div>
    )
  }

  return (
    <div
      lang={sessionLangAttr}
      dir={sessionDir}
      className={cn(
        'fixed inset-0 z-50 flex h-[100dvh] min-h-0 flex-col bg-[color:var(--sanadi-shell-bg)] text-foreground',
        preferredSessionLang === 'ar' && notoSansArabic.className,
      )}
    >
      {(voiceRecording || micListening) && (
        <div
          className={cn(
            'pointer-events-none fixed left-3 z-[120] flex items-center gap-2 rounded-full bg-black/50 px-2.5 py-1 text-[0.65rem] font-medium text-white md:left-4',
            voiceModeActive ? 'top-[3.75rem]' : 'top-16',
          )}
          role="status"
          aria-live="polite"
        >
          <span aria-hidden>●</span>
          <span>Recording</span>
          <span className="sr-only">Microphone is active</span>
        </div>
      )}

      <header className="relative z-[70] flex h-14 max-h-14 shrink-0 items-center justify-between border-b border-border/30 bg-[color:var(--sanadi-shell-bg)] px-3 md:px-4">
        <span className="text-base font-semibold tracking-tight text-primary md:text-lg">سنَدي Sanadi</span>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5 md:gap-2">
          <LanguagePicker value={preferredSessionLang} disabled onChange={() => {}} />
          <Button
            type="button"
            size="sm"
            variant={voiceModeActive ? 'secondary' : 'outline'}
            className="h-8 gap-1 rounded-full px-3 text-xs md:h-9 md:text-sm"
            aria-label="Voice mode"
            aria-pressed={voiceModeActive}
            onClick={() => setVoiceModeActive((v) => !v)}
          >
            <Headphones className="h-3.5 w-3.5 shrink-0 md:h-4 md:w-4" />
            Voice
          </Button>
          <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-health-success/80" title="Live" aria-hidden />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-row">
        <aside
          className={cn(
            'hidden min-h-0 shrink-0 flex-col border-r border-border/30 bg-muted/30 transition-[width] duration-200 ease-out md:flex',
            voiceModeActive && 'relative z-[65]',
            railCollapsed ? 'h-full w-[60px] items-center px-0 py-3' : 'h-full min-h-0 w-64 overflow-hidden p-3',
          )}
        >
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn('shrink-0 rounded-full', !railCollapsed && 'mb-2')}
            onClick={() => setRailCollapsed((c) => !c)}
            aria-label={railCollapsed ? 'Expand session panel' : 'Collapse session panel'}
          >
            {railCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          </Button>
          {!railCollapsed ? (
            <div className="flex min-h-0 flex-1 flex-col gap-0">
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain pr-1 [scrollbar-gutter:stable]">
                <div className="space-y-1 pb-4">
                  <p className="text-sm font-semibold text-foreground">{user?.username ?? 'You'}</p>
                  <p className="text-xs text-muted-foreground">Session {visitOrdinal}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                  </p>
                </div>
                <div className="mx-auto mb-5 flex flex-col items-center gap-2">
                  <SanadiMoodRing
                    emotion={displayEmotion?.label ?? null}
                    distressScore={latestResult?.fusion?.distress_score ?? latestResult?.distress_score}
                    className="h-16 w-16 rounded-full shadow-md ring-4 ring-white/70 dark:ring-white/10"
                  />
                </div>
                <Collapsible open={cameraPanelOpen} onOpenChange={setCameraPanelOpen} className="w-full shrink-0">
                  <CollapsibleTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className="mb-1 flex h-11 w-full items-center justify-between gap-2 rounded-2xl px-4 text-left text-xs font-medium shadow-sm"
                    >
                      <span>Camera (optional)</span>
                      <ChevronDown className={cn('h-4 w-4 shrink-0 opacity-70 transition-transform', cameraPanelOpen && 'rotate-180')} />
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="space-y-3 pb-4 data-[state=closed]:animate-none">
                    <p className="text-[0.7rem] leading-relaxed text-muted-foreground">
                      Optional preview. You control when your camera runs; nothing is inferred from visuals here.
                    </p>
                    <Button
                      type="button"
                      variant="secondary"
                      className="w-full rounded-2xl shadow-sm"
                      onClick={() => (cameraOn ? stopCamera() : void startCamera())}
                    >
                      {cameraOn ? (
                        <>
                          <CameraOff className="mr-2 inline-block h-4 w-4 align-middle" aria-hidden /> Turn preview off
                        </>
                      ) : (
                        <>
                          <Video className="mr-2 inline-block h-4 w-4 align-middle" aria-hidden /> Turn preview on
                        </>
                      )}
                    </Button>
                    <video ref={videoRef} className="mx-auto h-40 w-full max-w-[240px] rounded-xl bg-black object-cover shadow-inner" playsInline muted />
                  </CollapsibleContent>
                </Collapsible>
                <Collapsible open={recognitionDebugOpen} onOpenChange={setRecognitionDebugOpen} className="w-full shrink-0 pb-6 pt-3">
                  <CollapsibleTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className="flex h-10 w-full items-center justify-between gap-2 rounded-2xl px-3 text-left text-[0.65rem] font-medium text-muted-foreground shadow-sm"
                    >
                      <span>Recognition debug</span>
                      <ChevronDown
                        className={cn(
                          'h-3.5 w-3.5 shrink-0 opacity-70 transition-transform',
                          recognitionDebugOpen && 'rotate-180',
                        )}
                      />
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="pb-1 pt-2 data-[state=closed]:animate-none">
                  <p className="mb-2 text-[0.6rem] leading-snug text-muted-foreground">
                    Console logs mirror this view. Speech appears when you use Voice/STT (`speech_transcript` + optional `speech_audio`); modalities_used lists which channels influenced the reply.
                  </p>
                    <pre className="max-h-72 overflow-auto rounded-xl border border-border bg-background/90 p-2.5 font-mono text-[0.6rem] leading-relaxed text-foreground whitespace-pre-wrap wrap-break-word">
                      {recognitionDebugText}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              </div>
              {!voiceModeActive && (
                <div className="shrink-0 border-t border-border/40 bg-muted/25 pt-3 dark:bg-muted/15">
                  <Button type="button" variant="outline" className="w-full rounded-2xl" onClick={() => void closeSession()}>
                    End session
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-2 flex flex-1 flex-col items-center gap-3">
              <SanadiMoodRing
                emotion={displayEmotion?.label ?? null}
                distressScore={latestResult?.fusion?.distress_score ?? latestResult?.distress_score}
                className="h-9 w-9 rounded-full shadow ring-2 ring-white/50 dark:ring-white/10"
              />
              {!voiceModeActive && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-auto rounded-full px-2 text-[0.65rem]"
                  onClick={() => void closeSession()}
                  aria-label="End session"
                >
                  End
                </Button>
              )}
            </div>
          )}
        </aside>

        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          {voiceModeActive ? (
            <>
              <div className="flex shrink-0 items-center gap-3 border-b border-border/20 px-4 py-2 text-xs text-muted-foreground md:hidden">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">{user?.username ?? 'You'}</p>
                  <p className="truncate text-[0.65rem]">
                    Session {visitOrdinal} ·{' '}
                    {new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </p>
                </div>
                <SanadiMoodRing
                  emotion={displayEmotion?.label ?? null}
                  distressScore={latestResult?.fusion?.distress_score ?? latestResult?.distress_score}
                  className="h-10 w-10 shrink-0 rounded-full ring-2 ring-border/40"
                />
              </div>

              <div className="flex min-h-0 flex-1 flex-col">
                <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4 py-3">
                  <div className="flex w-full max-w-lg flex-col items-center justify-center gap-0">
                    <div className="flex min-h-[min(52svh,480px)] max-h-[60svh] w-full max-w-[min(92vw,28rem)] flex-1 flex-col items-center justify-end">
                      <SanadiTalkingHead
                        ref={talkingHeadRef}
                        active
                        variant="voiceHero"
                        phase={avatarPhase}
                        emotion={displayEmotion?.label ?? null}
                        distressScore={latestResult?.fusion?.distress_score ?? latestResult?.distress_score}
                        onAssistantAnalyser={onTalkingHeadAnalyserNode}
                      />
                    </div>
                    <p className="mt-2 text-center text-sm font-medium text-muted-foreground">{voicePhaseLine}</p>

                    <div className="mt-2 w-full max-w-[480px] shrink-0 overflow-hidden rounded-3xl border border-border/50 bg-background/90">
                      <div className="px-3 pt-3 pb-1">
                        <SanadiVoiceWaveform
                          analyserRef={voiceAnalyserRef}
                          speaker={waveSpeaker}
                          height={80}
                          className="opacity-95"
                        />
                      </div>
                      <Button
                        type="button"
                        className="h-auto w-full rounded-none border-0 border-t border-border/40 py-6 text-base font-semibold shadow-none"
                        disabled={loading || startingSession}
                        onClick={() => (voiceRecording ? stopVoiceRecordingTurn() : void startVoiceRecordingTurn())}
                      >
                        {voiceRecording ? 'Done speaking' : 'Tap to speak'}
                      </Button>
                    </div>
                    <p className="mt-2 max-w-[480px] text-center text-[0.65rem] leading-snug text-muted-foreground">
                      Groq transcribes your clip. Replies use calm voice when server TTS is on — turn Voice off to type in chat.
                    </p>
                  </div>
                </div>
              </div>

              <footer className="shrink-0 border-t border-border/30 bg-[color:var(--sanadi-shell-bg)] px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full rounded-2xl py-6"
                  onClick={() => void closeSession()}
                >
                  End session
                </Button>
                {chatError && <p className="mt-2 text-center text-xs text-muted-foreground">{chatError}</p>}
              </footer>
            </>
          ) : (
            <>
          <main ref={chatScrollRef} className="relative z-10 flex-1 overflow-y-auto px-3 py-4 md:px-5">
            <div className="mx-auto flex w-full max-w-5xl gap-4">
              <div className="mx-auto flex min-w-0 max-w-2xl flex-1 flex-col gap-3.5">
          {chat.map((entry) => (
            <div
              key={entry.id}
              title={new Date(entry.createdAt).toLocaleString()}
              className={`flex w-full ${entry.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
            >
              {entry.kind === 'thought_record' ? (
                <div className="w-[min(42rem,90vw)] rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-sm">
                  <p className="mb-3 text-sm font-medium">Thought record</p>
                  <div className="space-y-2">
                    <label className="block text-xs text-muted-foreground">What happened</label>
                    <textarea
                      className="w-full rounded-xl border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.event || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), event: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">What I thought</label>
                    <textarea
                      className="w-full rounded-xl border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.thought || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), thought: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">How it made me feel</label>
                    <textarea
                      className="w-full rounded-xl border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.feeling || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), feeling: e.target.value } }))}
                    />
                    <label className="block text-xs text-muted-foreground">Another way to see it</label>
                    <textarea
                      className="w-full rounded-xl border bg-background p-2 text-sm"
                      value={thoughtRecordByMessage[entry.id]?.reframe || ''}
                      onChange={(e) => setThoughtRecordByMessage((old) => ({ ...old, [entry.id]: { ...(old[entry.id] || { event: '', thought: '', feeling: '', reframe: '' }), reframe: e.target.value } }))}
                    />
                  </div>
                </div>
              ) : entry.role === 'assistant' ? (
                <div className="flex max-w-[90%] items-start gap-2.5">
                  <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[color:var(--sanadi-chat-assistant)] shadow-md ring-1 ring-border">
                    <Sparkles className="h-4 w-4 text-primary" />
                  </div>
                  <div className="rounded-[1.65rem] border border-border bg-[color:var(--sanadi-chat-assistant)] px-5 py-3.5 text-left text-[1.02rem] leading-relaxed text-foreground shadow-md">
                    {entry.content}
                  </div>
                </div>
              ) : (
                <div className="max-w-[84%] rounded-[1.65rem] border border-border bg-[color:var(--sanadi-chat-patient)] px-4 py-3 text-left text-sm leading-relaxed text-foreground shadow-md">
                  {entry.content}
                </div>
              )}
            </div>
          ))}
              </div>
            </div>
          </main>

          <footer className="relative z-[80] shrink-0 border-t border-border/30 bg-[color:var(--sanadi-shell-bg)] px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            <div className="mx-auto flex w-full max-w-2xl items-end gap-2">
              <Button
                type="button"
                size="icon"
                variant={micListening ? 'secondary' : 'outline'}
                className="h-12 w-12 shrink-0 rounded-2xl"
                onClick={() => toggleMic()}
              >
                <Mic className="h-5 w-5" />
              </Button>
              <textarea
                value={input}
                placeholder="Say anything..."
                rows={1}
                className="max-h-40 min-h-12 flex-1 resize-y rounded-2xl border border-border bg-background px-3 py-3 text-sm outline-none"
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void submitMessage()
                  }
                }}
              />
              <Button
                type="button"
                size="icon"
                className="h-12 w-12 shrink-0 rounded-2xl"
                onClick={() => void submitMessage()}
                disabled={loading || startingSession || !input.trim() || voiceRecording}
              >
                <SendHorizonal className="h-5 w-5" />
              </Button>
            </div>
            {chatError && <p className="mx-auto mt-2 w-full max-w-2xl text-xs text-muted-foreground">{chatError}</p>}
          </footer>
            </>
          )}
        </div>
      </div>
    </div>

  )
}
