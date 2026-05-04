import { fetchWithAuthRefresh, getApiUrls } from '@/lib/auth'

const base = () => getApiUrls().django.replace(/\/$/, '')

const apiPrefix = () => process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'

async function getJson<T>(path: string) {
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}${path}`, {
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function postJson<T>(path: string, body: unknown) {
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function postForm<T>(path: string, formData: FormData) {
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

async function deleteJson<T>(path: string) {
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}${path}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export type KidsProfile = {
  assistant_name: string
  persona_prompt: string
  avatar_prompt: string
  avatar_image_url: string
  parent_voice_sample_url: string
  parent_voice_profile_id: string
  child_reference_photos: string[]
  story_preferences: Record<string, unknown>
  updated_at: string
}

export type KidsState = {
  profile: KidsProfile
  active_instruction_doc: { id: number; source_filename: string; rules: string[] } | null
  latest_checkin: {
    id: number
    child_message: string
    followed_instructions: boolean
    lie_risk_score: number
    assistant_feedback: string
    created_at: string
  } | null
  latest_story: {
    id: number
    mood: string
    title: string
    narrative: string
    scene_image_prompt: string
    scene_image_url: string
    metadata: Record<string, unknown>
    created_at: string
  } | null
  latest_assistant_assessment: {
    complete: boolean
    followed: boolean
    lie_risk_score: number
    feedback: string
    story_direction: string
    had_avoid_items: string[]
    missed_do_items: string[]
    alert_items: string[]
    missing_items: string[]
  } | null
  recent_assistant_turns: {
    id: number
    child_message: string
    assistant_reply: string
    checklist_state: Record<string, string>
    provider: string
    model: string
    created_at: string
  }[]
}

export const getKidsState = () => getJson<KidsState>('/kids/state')
export const saveKidsProfile = (body: Partial<KidsProfile>) => postJson<KidsProfile>('/kids/profile', body)
export const sendKidsAssistantMessage = (body: { message: string }) =>
  postJson<{
    reply: string
    provider: string
    model: string
    rules_used: string[]
    checklist: Record<string, string[]>
    checklist_state: Record<string, string>
    missing_items: string[]
    next_question: string
    assessment: NonNullable<KidsState['latest_assistant_assessment']>
    checkin: KidsState['latest_checkin']
    turn_id: number
    rag_context: string
  }>(
    '/kids/assistant/message',
    body
  )
export const deleteKidsAssistantHistory = () => deleteJson<{ deleted_count: number }>('/kids/assistant/history')
export const generateKidsAvatar = (body: { prompt: string }) =>
  postJson<{ profile: KidsProfile; image_url: string; model: string; prompt: string; status: string }>('/kids/avatar/generate', body)
export const generateKidsStory = (body: { checkin_id?: number; prompt?: string }) =>
  postJson<KidsState['latest_story']>('/kids/story/generate', body)

export async function uploadKidsPdf(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}/kids/instructions/upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<{ document_id: number; source_filename: string; rules_count: number; rules: string[] }>
}

export function uploadParentVoice(file: Blob) {
  const formData = new FormData()
  const extension = file.type.includes('wav') ? 'wav' : 'webm'
  formData.append('file', file, `parent-voice.${extension}`)
  return postForm<KidsProfile>('/kids/parent-voice/upload', formData)
}

export async function synthesizeParentVoice(text: string) {
  const response = await fetchWithAuthRefresh(`${base()}${apiPrefix()}/kids/parent-voice/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text }),
  })
  const errText = async () => (await response.clone().text()).slice(0, 800)
  if (!response.ok) {
    throw new Error(await errText())
  }

  const contentType = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase()
  if (contentType === 'application/json') {
    throw new Error(await errText())
  }

  const buf = await response.arrayBuffer()
  if (buf.byteLength < 256) {
    const asText = new TextDecoder().decode(buf.slice(0, 512))
    if (asText.trim().startsWith('{') || asText.includes('"detail"')) {
      throw new Error(asText)
    }
  }

  const mime =
    contentType && contentType !== 'application/octet-stream'
      ? contentType
      : buf.byteLength >= 4 && new Uint8Array(buf.slice(0, 4))[0] === 0xff
        ? 'audio/mpeg'
        : 'audio/wav'

  const blob = new Blob([buf], { type: mime })

  return {
    blob,
    provider: (response.headers.get('X-Voice-Clone-Provider') || response.headers.get('x-voice-clone-provider') || '').trim(),
    voiceId: (response.headers.get('X-Voice-Id') || response.headers.get('x-voice-id') || '').trim(),
  }
}

export function uploadChildPhoto(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return postForm<KidsProfile>('/kids/child-photos/upload', formData)
}

export function uploadLieDetect(file: File) {
  const formData = new FormData()
  formData.append('file', file, file.name || 'capture.jpg')
  return postForm<{
    media_url: string
    attributes: any | null
    attributes_summary?: Record<string, unknown>
    lie_risk_score: number
  }>('/kids/lie-detect', formData)
}
