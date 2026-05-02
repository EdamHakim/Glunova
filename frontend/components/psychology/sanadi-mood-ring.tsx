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

  const gradient: Record<AvatarEmotion, string> = {
    neutral: 'conic-gradient(from 210deg, #94c9b8 0%, #d9e8e3 35%, #7fd4c9 70%, #94c9b8 100%)',
    happy: 'conic-gradient(from 40deg, #e8bc7a 0%, #f9eacf 45%, #d4a373 75%, #e8bc7a 100%)',
    anxious: 'conic-gradient(from 180deg, #8ecff0 0%, #dfeef8 45%, #5aaedc 78%, #8ecff0 100%)',
    distressed: 'conic-gradient(from 320deg, #e8b0a8 0%, #fdd 40%, #c26d6d 72%, #e8b0a8 100%)',
    depressed: 'conic-gradient(from 260deg, #aab8e8 0%, #e8e8f8 42%, #7b8fd4 74%, #aab8e8 100%)',
  }

  return (
    <div
      className={className}
      aria-hidden
      style={{
        background: gradient[em],
        boxShadow: '0 0 0 3px rgba(255,248,237,0.55) inset',
      }}
    />
  )
}
