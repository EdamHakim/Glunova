'use client'

import { cn } from '@/lib/utils'

export type AvatarPhase = 'idle' | 'listening' | 'thinking' | 'speaking'

export type AvatarEmotion = 'neutral' | 'happy' | 'anxious' | 'distressed' | 'depressed'

type Props = {
  phase: AvatarPhase
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  variant?: 'inline' | 'overlay'
  className?: string
}

const emotionGlow: Record<AvatarEmotion, string> = {
  neutral: 'from-teal-600/38 via-teal-100/15 to-amber-100/35',
  happy: 'from-amber-500/42 via-orange-400/22 to-transparent',
  anxious: 'from-sky-500/37 via-blue-600/14 to-transparent',
  distressed: 'from-rose-500/40 via-fuchsia-500/16 to-transparent',
  depressed: 'from-indigo-500/45 via-violet-600/20 to-transparent',
}

function deriveEmotion(e: AvatarEmotion | null | undefined, distress?: number | null): AvatarEmotion {
  const base = e && emotionGlow[e] ? e : ('neutral' as AvatarEmotion)
  if (typeof distress !== 'number' || !Number.isFinite(distress)) return base
  if (distress >= 0.85 && base === 'neutral') return 'distressed'
  return base
}

export function SanadiAvatar({ phase, emotion, distressScore, variant = 'inline', className }: Props) {
  const em = deriveEmotion(emotion, distressScore)
  const radial = emotionGlow[em]

  let phaseAnnouncement = ''
  if (phase === 'listening') phaseAnnouncement = 'Sanadi is listening'
  else if (phase === 'thinking') phaseAnnouncement = 'Sanadi is thinking'
  else if (phase === 'speaking') phaseAnnouncement = 'Sanadi is speaking'
  else phaseAnnouncement = 'Sanadi companion'

  const mouthStretch = phase === 'speaking' ? 'scale-y-[1.85] rounded-md' : 'scale-y-[0.85] rounded-full'
  const listenPulse = phase === 'listening'
  const sizeClass = variant === 'overlay' ? 'w-[min(22rem,88vw)]' : 'w-[min(16rem,70vw)]'
  const breathAnim =
    variant === 'overlay'
      ? 'animate-[sanadiBreath_4.3s_ease-in-out_infinite]'
      : 'animate-[sanadiBreath_4.9s_ease-in-out_infinite]'

  return (
    <section
      className={cn('relative flex flex-col items-center', className)}
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
          'relative aspect-square max-w-none rounded-[2rem] bg-gradient-to-b p-6 shadow-[0_22px_50px_-24px_rgb(94_66_43/0.35)] ring-2 ring-orange-950/10 dark:ring-orange-100/14',
          'motion-reduce:animate-none',
          breathAnim,
          sizeClass,
          radial,
          'transition-colors duration-500',
          phase === 'thinking' ? 'ring-amber-200/65' : '',
        )}
      >
        <div className="absolute inset-4 rounded-[1.65rem] bg-gradient-to-br from-amber-50/98 via-orange-50/90 to-amber-100/75 shadow-inner dark:from-muted/95 dark:to-muted/70" />

        <div className="relative mx-auto mt-8 flex h-24 w-[78%] flex-col items-center justify-start gap-3">
          <div className="flex w-[55%] justify-between px-3">
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-teal-900/82 transition-all dark:bg-amber-50/92',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-teal-900/82 transition-all dark:bg-amber-50/92',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDelay: phase === 'thinking' ? '0.12s' : undefined, animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
          </div>
          <div
            className={cn(
              'mx-auto mt-6 h-[0.52rem] w-[38%] origin-center bg-gradient-to-r from-transparent via-teal-900/78 to-transparent opacity-95 transition-all duration-150 dark:via-amber-50/90',
              mouthStretch,
              phase === 'speaking' ? 'animate-[pulse_160ms_ease-in-out_infinite]' : '',
            )}
          />
        </div>

        {listenPulse && (
          <div className="pointer-events-none absolute inset-0 animate-ping rounded-[2rem] bg-emerald-400/12 opacity-38 [animation-duration:2.2s]" />
        )}
      </div>
    </section>
  )
}
