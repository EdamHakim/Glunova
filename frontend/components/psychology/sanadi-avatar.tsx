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
  neutral: 'from-primary/38 via-accent/35 to-muted/40',
  happy: 'from-[color:var(--health-warning)]/40 via-chart-3/24 to-accent/35',
  anxious: 'from-secondary/38 via-primary/22 to-accent/28',
  distressed: 'from-destructive/40 via-health-danger/20 to-accent/25',
  depressed: 'from-[color:var(--psychology-soft-purple)]/42 via-accent/28 to-muted/35',
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
          'relative aspect-square max-w-none rounded-[2rem] bg-gradient-to-b p-6 shadow-[0_22px_50px_-24px_rgb(31_111_120/0.18)] ring-2 ring-border',
          'motion-reduce:animate-none',
          breathAnim,
          sizeClass,
          radial,
          'transition-colors duration-500',
          phase === 'thinking' ? 'ring-primary/45' : '',
        )}
      >
        <div className="absolute inset-4 rounded-[1.65rem] bg-gradient-to-br from-card via-accent/85 to-muted/80 shadow-inner dark:from-card/90 dark:via-accent/40 dark:to-muted/60" />

        <div className="relative mx-auto mt-8 flex h-24 w-[78%] flex-col items-center justify-start gap-3">
          <div className="flex w-[55%] justify-between px-3">
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-primary transition-all dark:bg-primary-foreground',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
            <span
              className={cn(
                'inline-block h-3.5 w-3.5 rounded-full bg-primary transition-all dark:bg-primary-foreground',
                phase === 'thinking' ? 'animate-bounce opacity-95' : 'opacity-95',
              )}
              style={{ animationDelay: phase === 'thinking' ? '0.12s' : undefined, animationDuration: phase === 'thinking' ? '0.85s' : undefined }}
            />
          </div>
          <div
            className={cn(
              'mx-auto mt-6 h-[0.52rem] w-[38%] origin-center bg-gradient-to-r from-transparent via-primary/82 to-transparent opacity-95 transition-all duration-150 dark:via-primary-foreground/92',
              mouthStretch,
              phase === 'speaking' ? 'animate-[pulse_160ms_ease-in-out_infinite]' : '',
            )}
          />
        </div>

        {listenPulse && (
          <div className="pointer-events-none absolute inset-0 animate-ping rounded-[2rem] bg-primary/15 opacity-38 [animation-duration:2.2s]" />
        )}
      </div>
    </section>
  )
}
