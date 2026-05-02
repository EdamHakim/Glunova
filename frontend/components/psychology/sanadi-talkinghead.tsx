'use client'

/**
 * TalkingHead — https://github.com/met4citizen/talkinghead — for Voice mode lipsync + service TTS.
 *
 * Default avatar: `public/mpfb.glb` → `/mpfb.glb`.
 * Override with `NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB` for another HTTPS or `/…` URL under `public/`.
 */

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { LipsyncEn } from '@met4citizen/talkinghead/modules/lipsync-en.mjs'
import { LipsyncFr } from '@met4citizen/talkinghead/modules/lipsync-fr.mjs'
import { cn } from '@/lib/utils'
import type { AvatarEmotion, AvatarPhase } from '@/components/psychology/sanadi-avatar'

/** Minimal surface for TalkingHead instance (no upstream .d.ts). */
type TalkingHeadInstance = {
  audioCtx: AudioContext
  audioAnalyzerNode: AnalyserNode
  /** Populated statically so webpack never has to resolve TalkingHead's dynamic `./lipsync-*.mjs` imports. */
  lipsync: Record<string, unknown>
  showAvatar: (opts: Record<string, unknown>, onProgress?: unknown) => Promise<void>
  setView?: (view: string, opts: Record<string, unknown>) => void
  setLighting?: (opts: Record<string, unknown>) => void
  setMixerGain?: (speech: number | null, bg: number | null, fadeSecs: number) => void
  setMood?: (mood: string) => void
  lookAtCamera?: (ms: number) => void
  speakAudio: (payload: Record<string, unknown>, opt?: Record<string, unknown>) => void
  stopSpeaking: () => void
  start: () => void
  dispose: () => void
}

export type PsychologyTtsLang = 'en' | 'fr' | 'ar' | 'darija' | 'mixed'

export type SanadiTalkingHeadHandle = {
  speakFromServiceTts: (
    blob: Blob,
    replyText: string,
    lang: PsychologyTtsLang,
    onEnded: () => void,
  ) => Promise<boolean>
  interruptSpeech: () => void
  isAvatarReady: () => boolean
}

type Props = {
  active: boolean
  phase: AvatarPhase
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  variant?: 'inline' | 'overlay'
  className?: string
  onAssistantAnalyser?: (node: AnalyserNode | null) => void
}

/** MPFB/MakeHuman companion mesh in `frontend/public/mpfb.glb`. */
const DEFAULT_AVATAR_SAME_ORIGIN_GLB = '/mpfb.glb'

function moodFromClinicalEmotion(
  emotion: AvatarEmotion | undefined | null,
  distressScore?: number | null,
): 'neutral' | 'happy' | 'angry' | 'sad' | 'fear' | 'disgust' | 'love' | 'sleep' {
  const elevated =
    typeof distressScore === 'number' && Number.isFinite(distressScore) && distressScore >= 0.82
  if (!emotion || emotion === 'neutral') return elevated ? 'sad' : 'neutral'
  if (emotion === 'happy') return 'happy'
  if (emotion === 'anxious') return 'fear'
  if (emotion === 'distressed') return elevated ? 'fear' : 'sad'
  if (emotion === 'depressed') return 'sad'
  return 'neutral'
}

function lipsyncLanguage(lang: PsychologyTtsLang): 'en' | 'fr' {
  if (lang === 'fr') return 'fr'
  return 'en'
}

function estimateWordTimeline(
  text: string,
  durationMs: number,
): { words: string[]; wtimes: number[]; wdurations: number[] } {
  const trimmed = text.trim()
  const words = trimmed ? trimmed.split(/\s+/).filter(Boolean) : ['']
  if (!words.length) {
    return { words: ['—'], wtimes: [0], wdurations: [Math.max(durationMs, 120)] }
  }

  const weights = words.map((w) => Math.max(1, w.replace(/\p{P}/gu, '').length) + 1.25)
  const sum = weights.reduce((a, b) => a + b, 0)
  let t = 0
  const wtimes: number[] = []
  const wdurations: number[] = []

  const target = Math.max(durationMs, words.length * 90)
  for (let i = 0; i < words.length; i++) {
    const wd = Math.max(90, (weights[i]! / sum) * target)
    wtimes.push(t)
    wdurations.push(wd)
    t += wd
  }
  const scale = target / Math.max(t, 1)
  let acc = 0
  for (let i = 0; i < words.length; i++) {
    wdurations[i] = wdurations[i]! * scale
    wtimes[i] = acc
    acc += wdurations[i]!
  }
  return { words, wtimes, wdurations }
}

export const SanadiTalkingHead = forwardRef<SanadiTalkingHeadHandle, Props>(function SanadiTalkingHead(
  { active, phase, emotion, distressScore, variant = 'overlay', className, onAssistantAnalyser },
  ref,
) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const headRef = useRef<TalkingHeadInstance | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)
  const [surfaceReady, setSurfaceReady] = useState(false)
  const avatarReadyRef = useRef(false)
  const disposedRef = useRef(false)
  const speechSafetyTimerRef = useRef<number | null>(null)
  const speechEndedOnceRef = useRef(false)

  const clearSpeechSafety = () => {
    if (speechSafetyTimerRef.current != null) {
      window.clearTimeout(speechSafetyTimerRef.current)
      speechSafetyTimerRef.current = null
    }
  }

  useImperativeHandle(
    ref,
    () => ({
      isAvatarReady: () => avatarReadyRef.current && !!headRef.current,
      interruptSpeech: () => {
        clearSpeechSafety()
        if (!headRef.current) return
        headRef.current.stopSpeaking()
      },
      speakFromServiceTts: async (blob, replyText, lang, onEnded) => {
        const head = headRef.current
        if (!avatarReadyRef.current || !head) return false
        clearSpeechSafety()
        speechEndedOnceRef.current = false
        head.stopSpeaking()

        let buffer: AudioBuffer
        try {
          const raw = await blob.arrayBuffer()
          const copy = raw.slice(0)
          buffer = await head.audioCtx.decodeAudioData(copy)
        } catch {
          return false
        }

        const durationMs = buffer.duration * 1000
        const { words, wtimes, wdurations } = estimateWordTimeline(replyText, durationMs)
        const lipsyncLang = lipsyncLanguage(lang)

        const finish = () => {
          if (speechEndedOnceRef.current || disposedRef.current) return
          speechEndedOnceRef.current = true
          clearSpeechSafety()
          onAssistantAnalyser?.(null)
          onEnded()
        }

        onAssistantAnalyser?.(head.audioAnalyzerNode)

        speechSafetyTimerRef.current = window.setTimeout(finish, Math.min(durationMs + 900, 120_000))

        head.speakAudio(
          {
            audio: buffer,
            words,
            wtimes,
            wdurations,
            markers: [finish],
            mtimes: [Math.max(0, durationMs - 80)],
          },
          { lipsyncLang },
        )
        try {
          head.lookAtCamera?.(400)
        } catch {
          /* optional */
        }
        return true
      },
    }),
    [onAssistantAnalyser],
  )

  useEffect(() => {
    if (!active) {
      disposedRef.current = false
      avatarReadyRef.current = false
      clearSpeechSafety()
      return
    }
    const el = mountRef.current
    if (!el || typeof window === 'undefined') return

    disposedRef.current = false
    avatarReadyRef.current = false
    setSurfaceReady(false)
    setBootError(null)

    let head: TalkingHeadInstance | null = null

    void (async () => {
      try {
        const mod = await import('@met4citizen/talkinghead/modules/talkinghead.mjs')
        const TalkingHead = mod.TalkingHead as new (node: HTMLElement, opts?: Record<string, unknown>) => TalkingHeadInstance

        head = new TalkingHead(el, {
          // Empty: default async import('./lipsync-*.mjs') breaks in the browser bundle; we attach processors below.
          lipsyncModules: [],
          lipsyncLang: 'en',
          cameraView: 'head',
          cameraRotateEnable: false,
          cameraPanEnable: false,
          cameraZoomEnable: false,
          modelMovementFactor: 0.42,
          avatarIdleEyeContact: 0.22,
          avatarIdleHeadMove: 0.28,
          avatarSpeakingEyeContact: 0.4,
          avatarSpeakingHeadMove: 0.28,
          modelPixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          lightAmbientIntensity: 2.85,
          lightDirectIntensity: 24,
          lightDirectColor: 0xaaacc8,
        })

        headRef.current = head
        head.lipsync.en = new LipsyncEn()
        head.lipsync.fr = new LipsyncFr()
        head.setMixerGain?.(2.55, null, 0)

        const avatarUrl =
          (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB?.trim()) ||
          DEFAULT_AVATAR_SAME_ORIGIN_GLB

        await head.showAvatar(
          {
            url: avatarUrl,
            body: 'M',
            avatarMood: 'neutral',
            lipsyncLang: 'en',
          },
          null,
        )

        head.setView?.('upper', {})

        head.setLighting?.({
          lightAmbientColor: 0xf4f6fa,
          lightAmbientIntensity: 2.95,
          lightDirectColor: 0xb8bdd4,
          lightDirectIntensity: 22,
          lightSpotIntensity: 0,
        })

        if (disposedRef.current || !headRef.current) {
          head.dispose()
          return
        }

        avatarReadyRef.current = true
        head.start()
        setSurfaceReady(true)
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        console.error('[SanadiTalkingHead]', e)
        setBootError(msg)
        setSurfaceReady(false)
      }
    })()

    return () => {
      disposedRef.current = true
      clearSpeechSafety()
      onAssistantAnalyser?.(null)
      avatarReadyRef.current = false
      setSurfaceReady(false)
      if (head) {
        try {
          head.dispose()
        } catch {
          /* ignore */
        }
        head = null
      }
      headRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount once per `active`; avoid re-fetching avatar
  }, [active])

  useEffect(() => {
    const head = headRef.current
    if (!head || !avatarReadyRef.current) return
    const mood = moodFromClinicalEmotion(emotion, distressScore)
    try {
      head.setMood?.(mood)
    } catch {
      /* ignore */
    }
  }, [emotion, distressScore])

  useEffect(() => {
    const head = headRef.current
    if (!head || !avatarReadyRef.current || phase !== 'thinking') return
    try {
      head.setMood?.('neutral')
    } catch {
      /* ignore */
    }
  }, [phase])

  if (!active) return null

  const sizeCls =
    variant === 'overlay' ? 'h-[min(28rem,88vw)] w-[min(24rem,92vw)]' : 'h-[min(20rem,65vw)] w-[min(18rem,70vw)]'

  let phaseAnnouncement = ''
  if (phase === 'listening') phaseAnnouncement = 'Sanadi is listening'
  else if (phase === 'thinking') phaseAnnouncement = 'Sanadi is thinking'
  else if (phase === 'speaking') phaseAnnouncement = 'Sanadi is speaking'
  else phaseAnnouncement = 'Sanadi companion'

  return (
    <section
      className={cn('relative flex flex-col items-center outline-none', className)}
      aria-labelledby="sanadi-th-label"
      role="application"
      aria-label="3D voice companion avatar"
    >
      <span id="sanadi-th-label" className="sr-only">
        {phaseAnnouncement}. Non-photorealistic companion visualization.
      </span>
      <div
        className={cn(
          'relative overflow-hidden rounded-[2rem] shadow-[0_22px_50px_-24px_rgb(31_111_120/0.14)] ring-2 ring-border/80',
          sizeCls,
        )}
      >
        <div ref={mountRef} className="relative h-full w-full bg-muted/35" />

        {(bootError || !surfaceReady) && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/40 px-6 text-center text-xs leading-relaxed text-muted-foreground">
            {bootError ? (
              <span>
                Companion model could not load ({bootError.slice(0, 140)}). You can set NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB
                to your own HTTPS GLB.
              </span>
            ) : (
              <span>Preparing calming companion avatar…</span>
            )}
          </div>
        )}
      </div>
    </section>
  )
})
