const base = () => {
  const psychologySpecific = process.env.NEXT_PUBLIC_PSYCHOLOGY_API_URL?.replace(/\/$/, '')
  if (psychologySpecific) return psychologySpecific
  const fastapiConfigured = process.env.NEXT_PUBLIC_FASTAPI_API_URL?.replace(/\/$/, '')
  if (fastapiConfigured) return fastapiConfigured
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8001`
  }
  return 'http://localhost:8001'
}

export const psychologyWsBase = () => {
  const b = base()
  if (b.startsWith('https://')) return `wss://${b.slice('https://'.length)}`
  if (b.startsWith('http://')) return `ws://${b.slice('http://'.length)}`
  return b.replace(/^http/, 'ws')
}

const psychologyPrefix = () => process.env.NEXT_PUBLIC_PSYCHOLOGY_PREFIX || '/psychology'

const fallbackBase = () => 'http://localhost:8001'

function withFallbackUrl(url: string): string | null {
  const fb = fallbackBase()
  if (url.startsWith(fb)) return null
  try {
    const parsed = new URL(url)
    return `${fb}${parsed.pathname}${parsed.search}`
  } catch {
    return null
  }
}

export type PsychologyMessagePayload = {
  session_id: string
  patient_id: number
  text: string
  face_emotion?: 'neutral' | 'anxious' | 'distressed' | 'depressed'
  face_confidence?: number
  speech_transcript?: string
  speech_emotion?: 'neutral' | 'anxious' | 'distressed' | 'depressed'
  speech_confidence?: number
  speech_audio_base64?: string
}

export type PsychologyMessageResult = {
  session_id: string
  reply: string
  emotion: 'neutral' | 'anxious' | 'distressed' | 'depressed'
  distress_score: number
  language_detected: 'en' | 'fr' | 'ar' | 'darija' | 'mixed'
  technique_used: string
  recommendation: string | null
  crisis_detected: boolean
  mental_state: 'Neutral' | 'Anxious' | 'Distressed' | 'Depressed' | 'Crisis'
  physician_review_required?: boolean
}

export type TrendPoint = {
  timestamp: string
  distress_score: number
  state: 'Neutral' | 'Anxious' | 'Distressed' | 'Depressed' | 'Crisis'
}

export type TrendResponse = {
  patient_id: number
  window_size: number
  slope: number
  points: TrendPoint[]
}

export type CrisisEvent = {
  id: string
  patient_id: number
  session_id: string
  probability: number
  action_taken: string
  created_at: string
  acknowledged_at?: string | null
}

export type SessionStartPayload = {
  session_id: string | null
  patient_id: number
  started_at: string | null
  memory_items_loaded: number
  allowed: boolean
  block_reason?: string | null
  physician_review_required?: boolean
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return (await response.json()) as T
}

async function fetchWithFallback(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init)
  } catch (error) {
    const fallbackUrl = withFallbackUrl(url)
    if (!fallbackUrl) throw error
    return fetch(fallbackUrl, init)
  }
}

export async function startPsychologySession(patientId: number, preferredLanguage = 'en') {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ patient_id: patientId, preferred_language: preferredLanguage }),
  })
  return parseJson<SessionStartPayload>(response)
}

export async function sendPsychologyMessage(payload: PsychologyMessagePayload) {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  })
  return parseJson<PsychologyMessageResult>(response)
}

export async function endPsychologySession(sessionId: string, patientId: number) {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ session_id: sessionId, patient_id: patientId }),
  })
  return parseJson<{ session_id: string; summary_stored: boolean }>(response)
}

export async function getPsychologyTrends(patientId: number) {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/trends/${patientId}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  return parseJson<TrendResponse>(response)
}

export async function listCrisisEvents(patientId?: number) {
  const url = new URL(`${base()}${psychologyPrefix()}/crisis/events`)
  if (patientId) {
    url.searchParams.set('patient_id', String(patientId))
  }
  const response = await fetchWithFallback(url.toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  const payload = await parseJson<{ items: CrisisEvent[] }>(response)
  return payload.items
}

export async function acknowledgeCrisisEvent(eventId: string, patientId?: number) {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/crisis/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ event_id: eventId, patient_id: patientId }),
  })
  return parseJson<{ ok: boolean }>(response)
}

export async function clearPhysicianSessionGate(patientId: number) {
  const response = await fetchWithFallback(`${base()}${psychologyPrefix()}/physician/clear-gate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ patient_id: patientId }),
  })
  return parseJson<{ ok: boolean }>(response)
}
