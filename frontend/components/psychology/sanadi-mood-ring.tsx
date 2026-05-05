'use client'

import type { AvatarEmotion } from '@/components/psychology/sanadi-avatar'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

type Props = {
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  /** Fusion confidence when available (0–1). */
  confidence?: number | null
  className?: string
}

const MOOD_LABEL: Record<AvatarEmotion, string> = {
  neutral: 'Neutral — settled',
  happy: 'Warm or upbeat',
  anxious: 'Tense or anxious',
  distressed: 'High distress signal',
  depressed: 'Low energy — heavy tone',
}

function pct01(x: number | undefined | null): string | null {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null
  return `${Math.round(Math.max(0, Math.min(1, x)) * 100)}%`
}

function resolveEffectiveEmotion(
  emotion: AvatarEmotion | null | undefined,
  distressScore?: number | null,
): AvatarEmotion {
  const raw =
    emotion && ['neutral', 'happy', 'anxious', 'distressed', 'depressed'].includes(emotion)
      ? emotion
      : 'neutral'
  let em: AvatarEmotion = raw as AvatarEmotion
  if (
    typeof distressScore === 'number' &&
    Number.isFinite(distressScore) &&
    distressScore >= 0.85 &&
    em === 'neutral'
  ) {
    em = 'distressed'
  }
  return em
}

/** Mood ring color; hover or focus opens a tooltip with readable mood details. */
export function SanadiMoodRing({ emotion, distressScore, confidence, className }: Props) {
  const effective = resolveEffectiveEmotion(emotion, distressScore)

  /* Hues from Glunova tokens: primary/secondary/accent/chart/health/psychology */
  const gradient: Record<AvatarEmotion, string> = {
    neutral: 'conic-gradient(from 210deg, #6fafb7 0%, #d9eef1 38%, #1f6f78 72%, #6fafb7 100%)',
    happy: 'conic-gradient(from 40deg, #e8d4bc 0%, #f4f7f8 42%, #d4a373 76%, #e8d4bc 100%)',
    anxious: 'conic-gradient(from 180deg, #9ec9ce 0%, #d9eef1 45%, #4c9a8a 78%, #9ec9ce 100%)',
    distressed: 'conic-gradient(from 320deg, #e0b5b0 0%, #f4e8e6 40%, #c26d6d 72%, #e0b5b0 100%)',
    depressed: 'conic-gradient(from 260deg, #c4bddc 0%, #e8e5f6 42%, #8a7eb0 74%, #c4bddc 100%)',
  }

  const confStr = pct01(confidence)
  const distressStr = pct01(distressScore)
  const awaiting = emotion == null && confStr === null && distressStr === null

  const ariaSummary = awaiting
    ? 'Mood ring; details appear after cues are detected.'
    : `Estimated mood: ${MOOD_LABEL[effective]}.${confStr ? ` Confidence ${confStr}.` : ''}${distressStr ? ` Distress cue ${distressStr}.` : ''}`

  return (
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <div
          className={cn(
            className,
            'cursor-help outline-none shrink-0 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          )}
          aria-label={ariaSummary}
          tabIndex={0}
          role="img"
          style={{
            background: gradient[effective],
            boxShadow: 'inset 0 0 0 3px color-mix(in srgb, var(--border) 70%, transparent)',
          }}
        />
      </TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={8} className="z-[160] max-w-[15rem] space-y-1.5 px-3 py-2 text-left shadow-lg">
        <p className="text-xs font-semibold leading-snug">Mood</p>
        {awaiting ? (
          <p className="text-xs leading-snug opacity-95">
            No estimate yet — the ring stays calm until cues arrive from chat, optional camera, or voice.
          </p>
        ) : (
          <p className="text-xs leading-snug opacity-95">{MOOD_LABEL[effective]}</p>
        )}
        {confStr ? (
          <p className="text-[0.7rem] leading-snug opacity-90">Confidence · {confStr}</p>
        ) : null}
        {distressStr ? (
          <p className="text-[0.7rem] leading-snug opacity-90">Distress cue · {distressStr}</p>
        ) : null}
        <p className="mt-0.5 border-t border-current/20 pt-1.5 text-[0.65rem] leading-snug opacity-80">
          Blended from your last cues (text, voice, optional camera).
        </p>
      </TooltipContent>
    </Tooltip>
  )
}
