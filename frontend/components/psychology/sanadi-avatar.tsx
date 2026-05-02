'use client'

import { cn } from '@/lib/utils'

export type AvatarPhase = 'idle' | 'listening' | 'thinking' | 'speaking'

export type AvatarEmotion = 'neutral' | 'happy' | 'anxious' | 'distressed' | 'depressed'

type Props = {
  phase: AvatarPhase
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  className?: string
}

const emotionGlow: Record<AvatarEmotion, string> = {
  neutral: 'from-teal-500/35 via-emerald-500/10 to-transparent',
  happy: 'from-amber-400/35 via-orange-400/15 to-transparent',
  anxious: 'from-sky-500/35 via-blue-600/15 to-transparent',
  distressed: 'from-rose-500/35 via-fuchsia-500/15 to-transparent',
  depressed: 'from-indigo-500/40 via-violet-600/20 to-transparent',
}

function deriveEmotion(e: AvatarEmotion | null | undefined, distress?: number | null): AvatarEmotion {
  const base = e && emotionGlow[e] ? e : ('neutral' as AvatarEmotion)
  if (typeof distress !== 'number' || !Number.isFinite(distress)) return base
  if (distress >= 0.85 && base === 'neutral') return 'distressed'
  return base
}

export function SanadiAvatar({ phase, emotion, distressScore, className }: Props) {
  const em = deriveEmotion(emotion, distressScore)
  const radial = emotionGlow[em]

  let phaseAnnouncement = ''
  if (phase === 'listening') phaseAnnouncement = 'Sanadi is listening'
  else if (phase === 'thinking') phaseAnnouncement = 'Sanadi is thinking'
  else if (phase === 'speaking') phaseAnnouncement = 'Sanadi is speaking'
  else phaseAnnouncement = 'Sanadi companion'

  const mouthStretch = phase === 'speaking' ? 'scale-y-[1.85] rounded-md' : 'scale-y-[0.85] rounded-full'
  const listenPulse = phase === 'listening'

  return (
    <section
      className={cn('relative flex flex-col items-center gap-2', className)}
      aria-labelledby="sanadi-avatar-label"
      role="img"
      aria-roledescription="companion illustration"
    >
      <span id="sanadi-avatar-label" className="sr-only">
        {phaseAnnouncement}
      </span>
      <div aria-live="polite" className="sr-only">
        {phaseAnnouncement}
      </div>
      <div
        className={cn(
          'relative aspect-square w-[min(16rem,70vw)] max-w-none rounded-[2rem] bg-gradient-to-b p-6 shadow-inner ring-2 ring-white/15',
          'transition-all duration-500',
          radial,
          phase === 'thinking' ? 'animate-pulse ring-violet-300/60' : 'ring-transparent',
          listenPulse ? 'animate-[pulse_1.6s_ease-in-out_infinite]' : '',
        )}
      >
        <div className="absolute inset-4 rounded-[1.65rem] bg-gradient-to-br from-muted/95 to-muted/65 shadow-md" />

        {/* Silhouette / face */}
        <div className="relative mx-auto mt-8 flex h-24 w-[78%] flex-col items-center justify-start gap-3">
          <div className="flex w-[55%] justify-between px-3">
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-slate-800/85 transition-all dark:bg-white/85',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-slate-800/85 transition-all dark:bg-white/85',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDelay: phase === 'thinking' ? '0.12s' : undefined, animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
          </div>
          {/* Mouth */}
          <div
            className={cn(
              'mx-auto mt-6 h-[0.52rem] w-[38%] origin-center bg-gradient-to-r from-transparent via-slate-800/80 to-transparent opacity-95 transition-all duration-150 dark:via-white/90',
              mouthStretch,
              phase === 'speaking' ? 'animate-[pulse_150ms_ease-in-out_infinite]' : '',
            )}
          />
        </div>

        {/* Subtle halo for listening */}
        {listenPulse && (
          <div className="pointer-events-none absolute inset-0 animate-ping rounded-[2rem] bg-emerald-400/10 opacity-40 [animation-duration:2.2s]" />
        )}
      </div>
      <p className="text-center text-[0.72rem] font-medium capitalize tracking-wide text-muted-foreground">
        {emotion ? `${emotion}${typeof distressScore === 'number' ? ` • ${Math.round(distressScore * 100)}% distress` : ''}` : '\u2014'}
      </p>
    </section>
  )
}
