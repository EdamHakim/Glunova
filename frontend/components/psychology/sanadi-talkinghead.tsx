'use client'

/**
 * TalkingHead — https://github.com/met4citizen/talkinghead — for Voice mode lipsync + service TTS.
 *
 * Default avatar: `public/mpfb.glb` (Avaturn export with Oculus `viseme_*` blendshapes on Head/Teeth/Tongue).
 * Override with `NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB` (e.g. `/api/sanadi-talkinghead-default` for RPM, or another `/…` / HTTPS GLB).
 * Bare `models.readyplayer.me/…glb` URLs get `morphTargets=ARKit,Oculus+Visemes,…` if missing (TalkingHead README).
 */

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
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
  /** Optional arm gestures while speaking (upstream uses prob 0.5 by default). */
  speakWithHands?: (delay?: number, prob?: number) => void
  /** Drive morphs directly (ARKit `jawOpen`, mixed `mouthOpen`, etc.); no-op if name missing. */
  setValue?: (mt: string, val: number, ms?: number | null) => void
  getMorphTargetNames?: () => string[]
  speakAudio: (payload: Record<string, unknown>, opt?: Record<string, unknown>) => void
  stopSpeaking: () => void
  start: () => void
  dispose: () => void
}

/** Fallback names when discovery finds nothing (ARKit / Oculus). */
const JAW_MORPH_CANDIDATES = ['jawOpen', 'mouthOpen', 'mouthFunnel', 'jawForward'] as const

/** When the GLB has `viseme_*` morphs, only nudge these with RMS — never `mouthOpen` / full mouth regex (fights `speakAudio`). */
const JAW_SUPPLEMENT_WHEN_VISEMES = ['jawOpen', 'jawForward'] as const

const MOUTH_NAME_RE = /jaw|mouth|lip|teeth|viseme|cheek|smile|frown|pucker|funnel|dimple|baa|oh|roll/i

/**
 * RMS-driven morphs for extra “life” when the model has no Oculus visemes; otherwise a tiny jaw supplement only.
 * Driving `viseme_*` (or all `mouth*`) from the analyser overwrites TalkingHead’s `speakAudio` viseme timeline.
 */
function discoverMouthMorphs(head: TalkingHeadInstance): string[] {
  const names = head.getMorphTargetNames?.() ?? []
  const set = new Set(names)
  const hasOculusVisemeMorphs = names.some((n) => /^viseme_/i.test(n))

  if (hasOculusVisemeMorphs) {
    const out: string[] = []
    for (const m of JAW_SUPPLEMENT_WHEN_VISEMES) {
      if (set.has(m)) out.push(m)
    }
    return out
  }

  const out: string[] = []
  for (const n of names) {
    if (MOUTH_NAME_RE.test(n)) out.push(n)
  }
  return [...new Set(out)]
}

async function decodeAudioBuffer(ctx: AudioContext, ab: ArrayBuffer): Promise<AudioBuffer> {
  const copy = ab.slice(0)
  try {
    return await ctx.decodeAudioData(copy)
  } catch (first) {
    try {
      return await new Promise<AudioBuffer>((resolve, reject) => {
        ctx.decodeAudioData(ab.slice(0), resolve, reject)
      })
    } catch {
      throw first
    }
  }
}

function runSpeakWithHands(head: TalkingHeadInstance, delay = 0, prob = 1) {
  try {
    head.speakWithHands?.(delay, prob)
  } catch {
    /* optional */
  }
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
  variant?: 'inline' | 'overlay' | 'voiceHero'
  className?: string
  onAssistantAnalyser?: (node: AnalyserNode | null) => void
}

/** Bundled avatar (`public/mpfb.glb`) — works offline; has `viseme_*` targets for TalkingHead `speakAudio`. */
const DEFAULT_AVATAR_SAME_ORIGIN_GLB = '/mpfb.glb'

/**
 * Ready Player Me must request ARKit + Oculus viseme morphs or TalkingHead cannot drive the mouth
 * (see https://github.com/met4citizen/TalkingHead examples/minimal.html `showAvatar.url`).
 */
function ensureReadyPlayerMeLipSyncMorphs(url: string): string {
  const s = url.trim()
  if (!s) return s
  try {
    const base =
      typeof window !== 'undefined' && window.location?.href ? window.location.href : 'http://localhost/'
    const u = new URL(s, base)
    const host = u.hostname.toLowerCase()
    if (!host.includes('readyplayer.me')) return s
    const morphTargets = u.searchParams.get('morphTargets') || ''
    if (/oculus/i.test(morphTargets) && /arkit/i.test(morphTargets)) return u.toString()
    u.searchParams.set(
      'morphTargets',
      'ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown',
    )
    if (!u.searchParams.has('textureSizeLimit')) u.searchParams.set('textureSizeLimit', '1024')
    if (!u.searchParams.has('textureFormat')) u.searchParams.set('textureFormat', 'png')
    return u.toString()
  } catch {
    return s
  }
}

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
  const safeDuration = Math.max(durationMs, 80)
  if (!words.length) {
    return { words: ['—'], wtimes: [0], wdurations: [safeDuration] }
  }

  const weights = words.map((w) => Math.max(1, w.replace(/\p{P}/gu, '').length) + 1.25)
  const sum = weights.reduce((a, b) => a + b, 0)
  // Per-word floor shrinks for dense or very short clips so total duration always matches audio
  // (TalkingHead viseme times must not run past the decoded buffer or sync feels broken).
  const minPerWord = Math.min(85, safeDuration / Math.max(words.length * 0.88, 1))
  const raw = words.map((_, i) => Math.max(minPerWord, (weights[i]! / sum) * safeDuration))
  const rawSum = raw.reduce((a, b) => a + b, 0)
  const scale = safeDuration / Math.max(rawSum, 1)
  const wdurations = raw.map((d) => d * scale)
  const wtimes: number[] = []
  let acc = 0
  for (let i = 0; i < words.length; i++) {
    wtimes.push(acc)
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
  const speechGestureTimersRef = useRef<number[]>([])
  const speechJawRafRef = useRef<number | null>(null)
  const mouthDriverMorphsRef = useRef<string[]>([])
  const speechEndedOnceRef = useRef(false)

  const clearSpeechGestureTimers = () => {
    for (const id of speechGestureTimersRef.current) {
      window.clearTimeout(id)
    }
    speechGestureTimersRef.current = []
  }

  const resetSpeechMotion = (head: TalkingHeadInstance) => {
    for (const m of mouthDriverMorphsRef.current) {
      try {
        head.setValue?.(m, 0, null)
      } catch {
        /* ignore */
      }
    }
    for (const m of JAW_MORPH_CANDIDATES) {
      try {
        head.setValue?.(m, 0, null)
      } catch {
        /* ignore */
      }
    }
    try {
      head.setValue?.('headRotateX', 0, null)
      head.setValue?.('headRotateY', 0, null)
      head.setValue?.('chestInhale', 0, null)
    } catch {
      /* ignore */
    }
  }

  const clearJawAudioDriver = () => {
    if (speechJawRafRef.current != null) {
      cancelAnimationFrame(speechJawRafRef.current)
      speechJawRafRef.current = null
    }
    const h = headRef.current
    if (h && avatarReadyRef.current) {
      resetSpeechMotion(h)
    }
  }

  const clearSpeechSafety = () => {
    clearSpeechGestureTimers()
    clearJawAudioDriver()
    if (speechSafetyTimerRef.current != null) {
      window.clearTimeout(speechSafetyTimerRef.current)
      speechSafetyTimerRef.current = null
    }
  }

  /**
   * Drive mouth + subtle head motion from the same analyser the library uses for speech.
   * Uses non-`viseme_*` mouth/jaw morphs so we do not fight TalkingHead’s own `speakAudio` viseme track.
   */
  function startJawAudioDriver(durationMs: number) {
    clearJawAudioDriver()
    const head = headRef.current
    if (!head) return
    const analyser = head.audioAnalyzerNode
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.28
    const td = new Float32Array(analyser.fftSize)
    const fd = new Uint8Array(analyser.frequencyBinCount)
    const deadline = performance.now() + durationMs + 600
    let smoothed = 0.04

    const tick = () => {
      const h = headRef.current
      if (!h || speechEndedOnceRef.current || disposedRef.current) {
        clearJawAudioDriver()
        return
      }
      if (performance.now() > deadline) {
        clearJawAudioDriver()
        return
      }
      try {
        analyser.getFloatTimeDomainData(td)
        analyser.getByteFrequencyData(fd)
        let sum = 0
        for (let i = 0; i < td.length; i++) {
          const s = td[i]!
          sum += s * s
        }
        const rms = Math.sqrt(sum / Math.max(td.length, 1))
        let peak = 0
        for (let i = 1; i < 56; i++) {
          if (fd[i]! > peak) peak = fd[i]!
        }
        const env = Math.max(rms * 6.5, peak / 255)
        const target = Math.min(0.95, Math.max(0, env * 1.35 + 0.03))
        smoothed += (target - smoothed) * 0.45
        const jaw = smoothed
        const morphs =
          mouthDriverMorphsRef.current.length > 0 ? mouthDriverMorphsRef.current : [...JAW_MORPH_CANDIDATES]
        for (const m of morphs) {
          const low = m.toLowerCase()
          const scale = /smile|dimple|cheek|press|pucker|roll|funnel/.test(low) ? 0.38 : 1
          h.setValue?.(m, jaw * scale, null)
        }
        const nod = Math.max(0, jaw - 0.05) * 0.22
        h.setValue?.('headRotateX', nod, null)
        h.setValue?.('headRotateY', Math.sin(performance.now() / 420) * nod * 0.55, null)
        h.setValue?.('chestInhale', jaw * 0.14, null)
      } catch {
        /* ignore */
      }
      speechJawRafRef.current = requestAnimationFrame(tick)
    }
    speechJawRafRef.current = requestAnimationFrame(tick)
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
          buffer = await decodeAudioBuffer(head.audioCtx, raw)
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

        await head.audioCtx.resume().catch(() => {})

        onAssistantAnalyser?.(head.audioAnalyzerNode)

        speechSafetyTimerRef.current = window.setTimeout(finish, Math.min(durationMs + 900, 120_000))

        try {
          head.speakAudio(
            {
              audio: buffer,
              words,
              wtimes,
              wdurations,
              markers: [finish],
              mtimes: [Math.max(120, durationMs - 40)],
            },
            { lipsyncLang },
          )
        } catch {
          clearSpeechSafety()
          return false
        }
        try {
          head.lookAtCamera?.(500)
        } catch {
          /* optional */
        }
        startJawAudioDriver(durationMs)
        // Library only rolls speakWithHands at 50% probability; force extra gestures so TTS feels alive.
        runSpeakWithHands(head, 0, 1)
        for (const at of [1100, 2400, 4000, 5800]) {
          if (at >= durationMs - 350) continue
          const tid = window.setTimeout(() => {
            if (speechEndedOnceRef.current || disposedRef.current) return
            runSpeakWithHands(head, 0, 1)
          }, at)
          speechGestureTimersRef.current.push(tid)
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
          modelMovementFactor: 0.58,
          avatarIdleEyeContact: 0.22,
          avatarIdleHeadMove: 0.28,
          avatarSpeakingEyeContact: 0.55,
          avatarSpeakingHeadMove: 0.46,
          modelPixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          lightAmbientIntensity: 2.85,
          lightDirectIntensity: 24,
          lightDirectColor: 0xaaacc8,
        })

        headRef.current = head
        const [lipsyncEnMod, lipsyncFrMod] = await Promise.all([
          import('@met4citizen/talkinghead/modules/lipsync-en.mjs'),
          import('@met4citizen/talkinghead/modules/lipsync-fr.mjs'),
        ])
        head.lipsync.en = new lipsyncEnMod.LipsyncEn()
        head.lipsync.fr = new lipsyncFrMod.LipsyncFr()
        head.setMixerGain?.(2.55, null, 0)

        const rawAvatarUrl =
          (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB?.trim()) ||
          DEFAULT_AVATAR_SAME_ORIGIN_GLB
        const avatarUrl = ensureReadyPlayerMeLipSyncMorphs(rawAvatarUrl)

        await head.showAvatar(
          {
            url: avatarUrl,
            body: 'F',
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

        mouthDriverMorphsRef.current = discoverMouthMorphs(head)

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
      mouthDriverMorphsRef.current = []
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
    // setMood resets every morph baseline — it wipes lip sync / jaw motion if it runs during TTS.
    if (phase === 'speaking') return
    const mood = moodFromClinicalEmotion(emotion, distressScore)
    try {
      head.setMood?.(mood)
    } catch {
      /* ignore */
    }
  }, [emotion, distressScore, phase])

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
    variant === 'voiceHero'
      ? 'h-[min(58svh,36rem)] w-[min(92vw,28rem)] max-h-[60vh]'
      : variant === 'overlay'
        ? 'h-[min(28rem,88vw)] w-[min(24rem,92vw)]'
        : 'h-[min(20rem,65vw)] w-[min(18rem,70vw)]'

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
          variant === 'voiceHero'
            ? 'relative overflow-hidden rounded-3xl bg-muted/15'
            : 'relative overflow-hidden rounded-[2rem] bg-gradient-to-b from-card/90 to-muted/50 shadow-[0_26px_56px_-22px_rgb(31_111_120/0.22)] ring-2 ring-primary/25 ring-offset-2 ring-offset-background',
          sizeCls,
        )}
      >
        <div
          ref={mountRef}
          className={cn(
            'relative h-full w-full',
            variant === 'voiceHero' ? 'bg-gradient-to-b from-primary/[0.04] to-transparent' : 'bg-gradient-to-b from-primary/[0.06] to-transparent',
          )}
        />

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
