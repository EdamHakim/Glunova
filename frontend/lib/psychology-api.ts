const base = () => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')
  if (configured) return configured
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

const psychologyPrefix = () => process.env.NEXT_PUBLIC_PSYCHOLOGY_PREFIX || '/psychology'

export type PsychologyMessagePayload = {
  session_id: string
  patient_id: number
  text: string
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
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return (await response.json()) as T
}

export async function startPsychologySession(patientId: number, preferredLanguage = 'en') {
  const response = await fetch(`${base()}${psychologyPrefix()}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ patient_id: patientId, preferred_language: preferredLanguage }),
  })
  return parseJson<{ session_id: string; patient_id: number; started_at: string }>(response)
}

export async function sendPsychologyMessage(payload: PsychologyMessagePayload) {
  const response = await fetch(`${base()}${psychologyPrefix()}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  })
  return parseJson<PsychologyMessageResult>(response)
}

export async function endPsychologySession(sessionId: string, patientId: number) {
  const response = await fetch(`${base()}${psychologyPrefix()}/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ session_id: sessionId, patient_id: patientId }),
  })
  return parseJson<{ session_id: string; summary_stored: boolean }>(response)
}

export async function getPsychologyTrends(patientId: number) {
  const response = await fetch(`${base()}${psychologyPrefix()}/trends/${patientId}`, {
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
  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })
  const payload = await parseJson<{ items: CrisisEvent[] }>(response)
  return payload.items
}
