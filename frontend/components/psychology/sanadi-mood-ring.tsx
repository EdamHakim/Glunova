'use client'

import type { AvatarEmotion } from '@/components/psychology/sanadi-avatar'

type Props = {
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  className?: string
}

/** Soft color ring only — no emotion labels (accessibility: decorative). */
export function SanadiMoodRing({ emotion, distressScore, className }: Props) {
  const raw = emotion && ['neutral', 'happy', 'anxious', 'distressed', 'depressed'].includes(emotion) ? emotion : 'neutral'
  let em: AvatarEmotion = raw as AvatarEmotion
  if (typeof distressScore === 'number' && Number.isFinite(distressScore) && distressScore >= 0.85 && em === 'neutral') {
    em = 'distressed'
  }

  /* Hues from Glunova tokens: primary/secondary/accent/chart/health/psychology */
  const gradient: Record<AvatarEmotion, string> = {
    neutral: 'conic-gradient(from 210deg, #6fafb7 0%, #d9eef1 38%, #1f6f78 72%, #6fafb7 100%)',
    happy: 'conic-gradient(from 40deg, #e8d4bc 0%, #f4f7f8 42%, #d4a373 76%, #e8d4bc 100%)',
    anxious: 'conic-gradient(from 180deg, #9ec9ce 0%, #d9eef1 45%, #4c9a8a 78%, #9ec9ce 100%)',
    distressed: 'conic-gradient(from 320deg, #e0b5b0 0%, #f4e8e6 40%, #c26d6d 72%, #e0b5b0 100%)',
    depressed: 'conic-gradient(from 260deg, #c4bddc 0%, #e8e5f6 42%, #8a7eb0 74%, #c4bddc 100%)',
  }

  return (
    <div
      className={className}
      aria-hidden
      style={{
        background: gradient[em],
        boxShadow: 'inset 0 0 0 3px color-mix(in srgb, var(--border) 70%, transparent)',
      }}
    />
  )
}
