'use client'

import { useEffect, useRef, useState } from 'react'
import { ExternalLink, ImagePlus, Loader2, Mic, Sparkles, Square, Trash2, Volume2, VolumeX } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  deleteKidsAssistantHistory,
  generateKidsAvatar,
  generateKidsStory,
  getKidsState,
  saveKidsProfile,
  sendKidsAssistantMessage,
  synthesizeParentVoice,
  uploadChildPhoto,
  uploadLieDetect,
  uploadKidsPdf,
  uploadParentVoice,
  type KidsProfile,
  type KidsState,
} from '@/lib/kids-api'

// Lie detector component removed from the dashboard UI; automatic check remains on Talk

type SpeechRecognitionEvent = Event & {
  results: {
    [index: number]: {
      [index: number]: { transcript: string }
    }
    length: number
  }
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
    SpeechRecognition?: new () => SpeechRecognitionLike
  }
}

export default function KidsPage() {
  const [state, setState] = useState<KidsState | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileUploading, setFileUploading] = useState(false)
  const [storyGenerating, setStoryGenerating] = useState(false)
  const [recording, setRecording] = useState(false)
  const [voicePreviewUrl, setVoicePreviewUrl] = useState<string | null>(null)
  const [voiceRecordingError, setVoiceRecordingError] = useState<string | null>(null)
  const [avatarGenerating, setAvatarGenerating] = useState(false)
  const [photoUploading, setPhotoUploading] = useState(false)
  const [assistantListening, setAssistantListening] = useState(false)
  const [assistantTranscript, setAssistantTranscript] = useState('')
  const [assistantReply, setAssistantReply] = useState('')
  const [assistantProvider, setAssistantProvider] = useState('')
  const [assistantMissingItems, setAssistantMissingItems] = useState<string[]>([])
  const [assistantThinking, setAssistantThinking] = useState(false)
  const [assistantSpeaking, setAssistantSpeaking] = useState(false)
  const [assistantVoiceStatus, setAssistantVoiceStatus] = useState('')
  const [useVoiceCloning, setUseVoiceCloning] = useState(true)
  const [clonePlaybackNeedsTap, setClonePlaybackNeedsTap] = useState(false)
  const [chatDeleting, setChatDeleting] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const voicePcmChunksRef = useRef<Float32Array[]>([])
  const voiceAudioContextRef = useRef<AudioContext | null>(null)
  const voiceProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const voiceStreamRef = useRef<MediaStream | null>(null)
  const speechRecognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const assistantAudioRef = useRef<HTMLAudioElement | null>(null)
  const cloneObjectUrlRef = useRef<string | null>(null)
  const lieCheckRef = useRef<{ checked: boolean; isLie: boolean } | null>(null)

  const revokeCloneObjectUrl = () => {
    if (cloneObjectUrlRef.current) {
      URL.revokeObjectURL(cloneObjectUrlRef.current)
      cloneObjectUrlRef.current = null
    }
  }

  const playPendingCloneAudio = () => {
    setClonePlaybackNeedsTap(false)
    const audio = assistantAudioRef.current
    if (!audio) return
    setAssistantSpeaking(true)
    void audio.play().catch((err: unknown) => {
      setAssistantSpeaking(false)
      setClonePlaybackNeedsTap(true)
      const detail = err instanceof Error ? err.message : 'playback failed'
      setAssistantVoiceStatus(`Could not play cloned audio: ${detail}`)
    })
  }

  useEffect(() => {
    void getKidsState()
      .then(setState)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load kids module'))
      .finally(() => setLoading(false))
  }, [])

  /** Helps Chrome/Safari allow later <audio>.play() after async LLM work (same tab, after user gesture). */
  useEffect(() => {
    let unlocked = false
    const warmAudioPlayback = () => {
      if (unlocked) return
      unlocked = true
      const silent =
        'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'
      const el = new Audio(silent)
      void el.play().catch(() => undefined)
      el.removeAttribute('src')
      window.removeEventListener('pointerdown', warmAudioPlayback, true)
      window.removeEventListener('keydown', warmAudioPlayback, true)
    }
    window.addEventListener('pointerdown', warmAudioPlayback, true)
    window.addEventListener('keydown', warmAudioPlayback, true)
    return () => {
      window.removeEventListener('pointerdown', warmAudioPlayback, true)
      window.removeEventListener('keydown', warmAudioPlayback, true)
    }
  }, [])

  useEffect(() => {
    return () => {
      if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl)
      revokeCloneObjectUrl()
      mediaRecorderRef.current?.stream.getTracks().forEach((track) => track.stop())
      voiceStreamRef.current?.getTracks().forEach((track) => track.stop())
      voiceAudioContextRef.current?.close()
      assistantAudioRef.current?.pause()
    }
  }, [voicePreviewUrl])

  const profile = state?.profile
  const latestStoryImageUrl =
    state?.latest_story?.scene_image_url &&
    !['local_svg_fallback', 'local_photo_cartoon'].includes(String(state.latest_story.metadata?.image_generation_mode || ''))
      ? state.latest_story.scene_image_url
      : ''

  const updateProfileField = (field: string, value: unknown) => {
    if (!state) return
    setState({ ...state, profile: { ...state.profile, [field]: value } })
  }

  const saveProfile = async () => {
    if (!state) return
    setSaving(true)
    setError(null)
    try {
      const updated = await saveKidsProfile({
        assistant_name: state.profile.assistant_name,
        persona_prompt: state.profile.persona_prompt,
        avatar_prompt: state.profile.avatar_prompt,
        avatar_image_url: state.profile.avatar_image_url,
        parent_voice_sample_url: state.profile.parent_voice_sample_url,
        parent_voice_profile_id: state.profile.parent_voice_profile_id,
        child_reference_photos: state.profile.child_reference_photos,
      })
      setState({ ...state, profile: updated })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save profile')
    } finally {
      setSaving(false)
    }
  }

  const encodeWav = (chunks: Float32Array[], sampleRate: number) => {
    const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
    const samples = new Float32Array(length)
    let offset = 0
    chunks.forEach((chunk) => {
      samples.set(chunk, offset)
      offset += chunk.length
    })

    const buffer = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(buffer)
    const writeString = (position: number, value: string) => {
      for (let i = 0; i < value.length; i += 1) view.setUint8(position + i, value.charCodeAt(i))
    }
    writeString(0, 'RIFF')
    view.setUint32(4, 36 + samples.length * 2, true)
    writeString(8, 'WAVE')
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    writeString(36, 'data')
    view.setUint32(40, samples.length * 2, true)

    let position = 44
    for (let i = 0; i < samples.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(position, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
      position += 2
    }
    return new Blob([buffer], { type: 'audio/wav' })
  }

  const startVoiceRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceRecordingError('Voice recording is not available in this browser.')
      return
    }

    try {
      setVoiceRecordingError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const audioContext = new AudioContext()
      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      voicePcmChunksRef.current = []
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0)
        voicePcmChunksRef.current.push(new Float32Array(input))
      }
      source.connect(processor)
      processor.connect(audioContext.destination)
      voiceStreamRef.current = stream
      voiceAudioContextRef.current = audioContext
      voiceProcessorRef.current = processor
      setRecording(true)
    } catch (err: unknown) {
      setVoiceRecordingError(err instanceof Error ? err.message : 'Could not start voice recording.')
    }
  }

  const stopVoiceRecording = () => {
    const audioContext = voiceAudioContextRef.current
    const processor = voiceProcessorRef.current
    processor?.disconnect()
    voiceStreamRef.current?.getTracks().forEach((track) => track.stop())
    const audioBlob = encodeWav(voicePcmChunksRef.current, audioContext?.sampleRate || 48000)
    if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl)
    setVoicePreviewUrl(URL.createObjectURL(audioBlob))
    void audioContext?.close()
    voiceAudioContextRef.current = null
    voiceProcessorRef.current = null
    voiceStreamRef.current = null
    voicePcmChunksRef.current = []
    void uploadParentVoice(audioBlob)
      .then((updated) => {
        if (state) setState({ ...state, profile: updated })
      })
      .catch((err: unknown) => setVoiceRecordingError(err instanceof Error ? err.message : 'Voice upload failed.'))
    setRecording(false)
  }

  const askAssistant = async (message: string) => {
    setAssistantThinking(true)
    setError(null)
    try {
      const response = await sendKidsAssistantMessage({ message })
      setAssistantReply(response.reply)
      setAssistantProvider(`${response.provider}${response.model ? ` • ${response.model}` : ''}`)
      setAssistantMissingItems(response.missing_items)
      const refreshed = await getKidsState()
      setState(refreshed)
      if (response.assessment?.complete && response.checkin?.id) {
        setStoryGenerating(true)
        await generateKidsStory({
          checkin_id: response.checkin.id,
          prompt: response.assessment.story_direction,
        })
        const storyState = await getKidsState()
        setState(storyState)
        setStoryGenerating(false)
      }
      void speak(response.reply, refreshed.profile)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Assistant message failed')
      setStoryGenerating(false)
    } finally {
      setAssistantThinking(false)
    }
  }

  const deleteChatHistory = async () => {
    if (!state?.recent_assistant_turns?.length || chatDeleting) return
    const confirmed = window.confirm('Delete Buddy chat history for this child? This will not delete stories, photos, PDFs, or check-ins.')
    if (!confirmed) return
    setChatDeleting(true)
    setError(null)
    try {
      await deleteKidsAssistantHistory()
      const refreshed = await getKidsState()
      setState(refreshed)
      setAssistantReply('')
      setAssistantProvider('')
      setAssistantMissingItems([])
      setAssistantTranscript('')
      setAssistantVoiceStatus('')
      setClonePlaybackNeedsTap(false)
      revokeCloneObjectUrl()
      window.speechSynthesis?.cancel()
      setAssistantSpeaking(false)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete chat history')
    } finally {
      setChatDeleting(false)
    }
  }

  const speakWithBrowserVoice = (message: string, statusMessage = 'Using browser voice fallback') => {
    setAssistantVoiceStatus(statusMessage)
    if (!('speechSynthesis' in window)) {
      setAssistantSpeaking(false)
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(message)
    utterance.rate = 0.95
    utterance.pitch = 1.05
    utterance.onstart = () => setAssistantSpeaking(true)
    utterance.onend = () => setAssistantSpeaking(false)
    utterance.onerror = () => setAssistantSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }

  const speak = async (message: string, voiceProfile?: KidsProfile | null) => {
    const vp = voiceProfile ?? profile
    if (!message.trim()) return
    setClonePlaybackNeedsTap(false)
    assistantAudioRef.current?.pause()
    revokeCloneObjectUrl()
    assistantAudioRef.current = null
    window.speechSynthesis?.cancel()
    if (!useVoiceCloning) {
      speakWithBrowserVoice(message, 'Voice cloning is off. Using browser voice')
      return
    }
    if (!vp?.parent_voice_sample_url) {
      setAssistantVoiceStatus('Record a parent voice sample to enable cloning')
      speakWithBrowserVoice(message)
      return
    }
    setAssistantSpeaking(true)
    setAssistantVoiceStatus('Generating parent voice clone audio...')
    try {
      const audioResult = await synthesizeParentVoice(message)
      const providerHint =
        audioResult.provider === 'fish'
          ? 'Fish Audio clone'
          : audioResult.provider === 'pocket'
            ? 'Kyutai Pocket TTS (local) clone'
            : audioResult.provider === 'elevenlabs'
              ? 'ElevenLabs clone'
              : audioResult.provider
                ? `Clone (${audioResult.provider})`
                : 'Cloned audio (set CORS_EXPOSE_HEADERS if provider is blank)'
      setAssistantVoiceStatus(`${providerHint} · ${audioResult.blob.size} bytes`)
      const audioUrl = URL.createObjectURL(audioResult.blob)
      cloneObjectUrlRef.current = audioUrl
      const audio = new Audio(audioUrl)
      assistantAudioRef.current = audio
      audio.onended = () => {
        setAssistantSpeaking(false)
        revokeCloneObjectUrl()
        assistantAudioRef.current = null
      }
      audio.onerror = () => {
        setAssistantSpeaking(false)
        revokeCloneObjectUrl()
        assistantAudioRef.current = null
        setAssistantVoiceStatus('Clone audio could not play')
      }
      try {
        await audio.play()
      } catch (playErr: unknown) {
        const blocked =
          playErr instanceof DOMException &&
          (playErr.name === 'NotAllowedError' || playErr.name === 'NotSupportedError')
        if (blocked) {
          setAssistantSpeaking(false)
          setClonePlaybackNeedsTap(true)
          setAssistantVoiceStatus(
            'Cloned voice is ready — tap Play cloned reply (the browser blocked autoplay after the assistant finished).'
          )
          return
        }
        throw playErr
      }
    } catch (err: unknown) {
      revokeCloneObjectUrl()
      assistantAudioRef.current = null
      const detail = err instanceof Error ? err.message : 'Voice clone failed'
      speakWithBrowserVoice(message, `Clone unavailable: ${detail.slice(0, 140)}. Falling back to browser voice`)
    }
  }

  const startAssistantListening = async () => {
    // try a quick camera snapshot and run the lie-detector before listening
    lieCheckRef.current = null
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const vStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 320, height: 240 } })
        const video = document.createElement('video')
        video.autoplay = true
        video.playsInline = true
        video.muted = true
        video.srcObject = vStream
        // wait a short time for the camera to warm up
        await new Promise((res) => {
          const t = setTimeout(() => res(null), 600)
          video.onloadedmetadata = () => {
            clearTimeout(t)
            res(null)
          }
        })
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth || 320
        canvas.height = video.videoHeight || 240
        const ctx = canvas.getContext('2d')
        if (ctx) ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const blob: Blob | null = await new Promise((resolve) => canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.8))
        vStream.getTracks().forEach((t) => t.stop())
        if (blob) {
          const file = new File([blob], 'capture.jpg', { type: blob.type })
          try {
            setAssistantThinking(true)
            const res = await uploadLieDetect(file)
            const lieRisk = typeof res?.lie_risk_score === 'number' ? res.lie_risk_score : 0
            const isLie = lieRisk >= 0.5
            lieCheckRef.current = { checked: true, isLie }
            if (isLie) {
              const polite = "Sorry, I don't think that's truthful. Can you try answering again?"
              setAssistantReply(polite)
              await speak(polite)
              // re-ask the assistant's question (same behavior as Ask me)
              try {
                await askAssistant('')
              } catch (e) {
                // ignore errors from re-ask
              }
              return
            }
          } catch (err) {
            // if lie-detect upload failed, continue to listening path
            lieCheckRef.current = { checked: false, isLie: false }
          } finally {
            setAssistantThinking(false)
          }
        }
      }
    } catch (err) {
      // camera access failed — continue to listening
      lieCheckRef.current = { checked: false, isLie: false }
    }

    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Recognition) {
      setError('Speech recognition is not available in this browser. You can still type your check-in below.')
      return
    }

    const recognition = new Recognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'
    recognition.onresult = (event) => {
      let transcript = event.results[0]?.[0]?.transcript || ''
      // if we ran lie-check and it reported truthful, append the "truth" flag
      if (lieCheckRef.current?.checked && !lieCheckRef.current.isLie) {
        transcript = `${transcript} truth`
      }
      setAssistantTranscript(transcript)
      void askAssistant(transcript)
    }
    recognition.onerror = () => {
      setAssistantListening(false)
      setError('I could not hear clearly. Please try again or type the check-in.')
    }
    recognition.onend = () => setAssistantListening(false)
    speechRecognitionRef.current = recognition
    setAssistantListening(true)
    recognition.start()
  }

  const stopAssistantListening = () => {
    speechRecognitionRef.current?.stop()
    setAssistantListening(false)
  }

  const generateAvatar = async () => {
    if (!state) return
    setAvatarGenerating(true)
    setError(null)
    try {
      const response = await generateKidsAvatar({ prompt: state.profile.avatar_prompt })
      setState({ ...state, profile: response.profile })
      if (!response.image_url) {
        setError('Avatar prompt saved. Add HUGGINGFACE_API_KEY to backend/.env to generate the image.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Avatar generation failed')
    } finally {
      setAvatarGenerating(false)
    }
  }

  const uploadPhoto = async (file: File | null) => {
    if (!file || !state) return
    setPhotoUploading(true)
    setError(null)
    try {
      const updated = await uploadChildPhoto(file)
      setState({ ...state, profile: updated })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Child photo upload failed')
    } finally {
      setPhotoUploading(false)
    }
  }

  const uploadPdf = async (file: File | null) => {
    if (!file) return
    setFileUploading(true)
    setError(null)
    try {
      await uploadKidsPdf(file)
      const refreshed = await getKidsState()
      setState(refreshed)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload PDF')
    } finally {
      setFileUploading(false)
    }
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Kids AI Assistant</h1>
        <p className="text-muted-foreground mt-2">
          Persistent child-safe assistant with PDF memory, persona setup, and daily story rewards.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && <p className="text-sm text-muted-foreground">Loading kids assistant state...</p>}

      {!loading && state && (
        <>
          <Card className="overflow-hidden">
            <CardContent className="grid gap-6 p-6 lg:grid-cols-[minmax(260px,360px)_1fr]">
              <div className="flex flex-col items-center justify-center gap-4 py-4 text-center">
                <div className="relative flex h-56 w-56 items-center justify-center rounded-full border bg-muted/40 shadow-inner">
                  {profile?.avatar_image_url ? (
                    <img
                      src={profile.avatar_image_url}
                      alt={`${profile?.assistant_name || 'Assistant'} avatar`}
                      className="h-full w-full rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-40 w-40 items-center justify-center rounded-full bg-gradient-to-br from-cyan-100 via-white to-emerald-100 text-primary">
                      <Sparkles className="h-16 w-16" />
                    </div>
                  )}
                  {(assistantListening || assistantSpeaking) && (
                    <span className="absolute inset-0 rounded-full border-4 border-primary/40 animate-pulse" />
                  )}
                </div>
                <div>
                  <p className="text-xl font-semibold">{profile?.assistant_name || 'Buddy'}</p>
                  <p className="text-sm text-muted-foreground">
                    {assistantListening
                      ? 'Listening...'
                      : assistantThinking
                        ? 'Thinking...'
                        : assistantSpeaking
                          ? 'Speaking...'
                          : 'Ready for today'}
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  <Button
                    type="button"
                    onClick={() => (assistantListening ? stopAssistantListening() : startAssistantListening())}
                    variant={assistantListening ? 'destructive' : 'default'}
                  >
                    {assistantListening ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                    {assistantListening ? 'Stop' : 'Talk'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => (assistantReply ? void speak(assistantReply) : void askAssistant(''))}
                    disabled={assistantThinking}
                  >
                    {assistantThinking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
                    {assistantReply ? 'Speak' : 'Ask me'}
                  </Button>
                  {clonePlaybackNeedsTap && (
                    <Button type="button" variant="secondary" onClick={() => playPendingCloneAudio()}>
                      <Volume2 className="h-4 w-4" />
                      Play cloned reply
                    </Button>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <CardTitle>Voice Assistant</CardTitle>
                      <CardDescription>
                        A ChatGPT-style voice surface for daily check-ins, using the chosen avatar and saved doctor rules.
                      </CardDescription>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void deleteChatHistory()}
                      disabled={chatDeleting || !state.recent_assistant_turns?.length}
                    >
                      {chatDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      {chatDeleting ? 'Deleting...' : 'Delete chat'}
                    </Button>
                    <Button
                      type="button"
                      variant={useVoiceCloning ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => {
                        setUseVoiceCloning((prev) => {
                          const next = !prev
                          setClonePlaybackNeedsTap(false)
                          assistantAudioRef.current?.pause()
                          revokeCloneObjectUrl()
                          assistantAudioRef.current = null
                          setAssistantSpeaking(false)
                          setAssistantVoiceStatus(
                            next ? 'Voice cloning enabled' : 'Voice cloning disabled. Using browser voice'
                          )
                          return next
                        })
                      }}
                    >
                      {useVoiceCloning ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                      {useVoiceCloning ? 'Cloning on' : 'Cloning off'}
                    </Button>
                  </div>
                </div>
                <div className="rounded-md border bg-muted/30 p-4 text-sm">
                  <p className="font-medium">{assistantReply ? 'Assistant reply' : 'Assistant question'}</p>
                  <p className="mt-1 text-muted-foreground">
                    {assistantReply ||
                      'Tap Ask me or Talk. I will read the doctor PDF rules and ask you a normal question about today.'}
                  </p>
                  {assistantProvider && <p className="mt-2 text-xs text-muted-foreground">LLM: {assistantProvider}</p>}
                  {assistantVoiceStatus && <p className="mt-1 text-xs text-muted-foreground">Voice: {assistantVoiceStatus}</p>}
                  {!!assistantMissingItems.length && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Still checking: {assistantMissingItems.map((item) => item.split(':').slice(1).join(':')).join(', ')}
                    </p>
                  )}
                </div>
                {!!state.recent_assistant_turns?.length && (
                  <div className="max-h-80 space-y-3 overflow-y-auto rounded-md border p-4 text-sm">
                    {state.recent_assistant_turns.map((turn) => (
                      <div key={turn.id} className="space-y-2">
                        {turn.child_message && (
                          <div className="ml-auto max-w-[85%] rounded-md bg-primary px-3 py-2 text-primary-foreground">
                            {turn.child_message}
                          </div>
                        )}
                        <div className="max-w-[85%] rounded-md bg-muted px-3 py-2 text-muted-foreground">
                          {turn.assistant_reply}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {assistantTranscript && (
                  <div className="rounded-md border p-4 text-sm">
                    <p className="font-medium">Voice transcript</p>
                    <p className="mt-1 text-muted-foreground">{assistantTranscript}</p>
                  </div>
                )}
                {profile?.parent_voice_sample_url && (
                  <div className="rounded-md border p-4 text-sm">
                    <p className="font-medium">Saved parent voice sample</p>
                    <audio controls src={profile.parent_voice_sample_url} className="mt-2 w-full" />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Day 1 Setup</CardTitle>
              <CardDescription>Upload doctor PDF, define persona, generate an avatar, and record the parent voice in-app.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="pdf-upload">Doctor instruction PDF</Label>
                <Input id="pdf-upload" type="file" accept="application/pdf" onChange={(e) => void uploadPdf(e.target.files?.[0] || null)} />
                <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                  <p className="font-medium text-foreground">Example doctor instruction for a child with diabetes</p>
                  <p className="mt-1">
                    No candy, soda, juice, or desserts with added sugar. Drink water, eat balanced meals with protein and
                    vegetables, check blood sugar before breakfast and bedtime, take insulin exactly as prescribed, and tell a
                    parent right away if feeling shaky, dizzy, very thirsty, or unusually tired.
                  </p>
                </div>
                {fileUploading && <p className="text-xs text-muted-foreground">Extracting rules and building memory index...</p>}
                {state.active_instruction_doc && (
                  <p className="text-xs text-muted-foreground">
                    Active file: {state.active_instruction_doc.source_filename} ({state.active_instruction_doc.rules.length} rules)
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Assistant name</Label>
                  <Input value={profile?.assistant_name || ''} onChange={(e) => updateProfileField('assistant_name', e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Avatar generation prompt</Label>
                  <Textarea
                    value={profile?.avatar_prompt || ''}
                    onChange={(e) => updateProfileField('avatar_prompt', e.target.value)}
                    placeholder="A friendly cartoon space helper with warm colors, soft eyes, and a playful medical badge"
                  />
                  <Button type="button" variant="outline" onClick={() => void generateAvatar()} disabled={avatarGenerating}>
                    {avatarGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
                    {avatarGenerating ? 'Generating...' : 'Generate avatar'}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Persona prompt (free text from child)</Label>
                <Textarea value={profile?.persona_prompt || ''} onChange={(e) => updateProfileField('persona_prompt', e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="child-photo-upload">Child story photos</Label>
                <Input
                  id="child-photo-upload"
                  type="file"
                  accept="image/*"
                  onChange={(e) => void uploadPhoto(e.target.files?.[0] || null)}
                />
                {photoUploading && <p className="text-xs text-muted-foreground">Saving child photo for story generation...</p>}
                {!!profile?.child_reference_photos?.length && (
                  <div className="flex flex-wrap gap-2">
                    {profile.child_reference_photos.map((photoUrl) => (
                      <img key={photoUrl} src={photoUrl} alt="Child reference" className="h-16 w-16 rounded-md border object-cover" />
                    ))}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  These photos are saved as protagonist references for later cartoon story scenes.
                </p>
              </div>
              <div className="space-y-2">
                <Label>Parent voice recording</Label>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant={recording ? 'destructive' : 'outline'}
                    onClick={() => (recording ? stopVoiceRecording() : void startVoiceRecording())}
                  >
                    {recording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                    {recording ? 'Stop recording' : 'Record voice'}
                  </Button>
                  {voicePreviewUrl && <audio controls src={voicePreviewUrl} className="h-10" />}
                </div>
                {voiceRecordingError && <p className="text-xs text-destructive">{voiceRecordingError}</p>}
                <p className="text-xs text-muted-foreground">
                  Parent can record their voice directly here instead of pasting a sample URL or profile ID.
                </p>
              </div>
              <Button onClick={() => void saveProfile()} disabled={saving}>
                {saving ? 'Saving...' : 'Save setup'}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Story</CardTitle>
              <CardDescription>Buddy generates this automatically when the check-in is complete.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {storyGenerating && <p className="text-sm text-muted-foreground">Generating story and image...</p>}
              {!storyGenerating && !state.latest_story && (
                <p className="text-sm text-muted-foreground">Finish Buddy&apos;s check-in and the story will appear here.</p>
              )}
              {state.latest_story && (
                <div className="space-y-3 rounded-lg border p-3">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{state.latest_story.title}</p>
                    <Badge variant="outline">{state.latest_story.mood}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{state.latest_story.narrative}</p>
                  {latestStoryImageUrl ? (
                    <div className="relative overflow-hidden rounded-md border bg-muted/20">
                      <img src={latestStoryImageUrl} alt="Story scene" className="max-h-[32rem] w-full object-contain" />
                      <Button asChild size="sm" variant="secondary" className="absolute right-3 top-3 shadow-sm">
                        <a href={latestStoryImageUrl} target="_blank" rel="noreferrer">
                          <ExternalLink className="h-4 w-4" />
                          Full size
                        </a>
                      </Button>
                    </div>
                  ) : (
                    <div className="rounded-md border border-dashed bg-muted/30 p-3 text-sm text-muted-foreground">
                      Story text was generated, but the cartoon image provider did not return an image.
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Standalone lie-detector UI removed — lie-check runs automatically when you click Talk */}
        </>
      )}
    </div>
  )
}
