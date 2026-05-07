'use client'

import { useEffect, useId, useState } from 'react'
import { Wind } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const PHASES = [
  { key: 'inhale', title: 'Breathe in', hint: 'Slowly through your nose for four counts.' },
  { key: 'hold1', title: 'Hold', hint: 'Gently hold — shoulders soft.' },
  { key: 'exhale', title: 'Breathe out', hint: 'Let the exhale be a little longer than the inhale.' },
  { key: 'hold2', title: 'Rest', hint: 'Brief pause before the next cycle.' },
] as const

const PHASE_MS = 4000

type Props = {
  className?: string
  onDismiss: () => void
}

/**
 * Gentle box-breathing cue for voice mode when distress is elevated.
 * 4×4s phases; outer ring animates in sync (CSS keyframes scoped by component id).
 */
export function SanadiBreathingCue({ className, onDismiss }: Props) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '') || 'breath'
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    const id = window.setInterval(() => {
      setPhase((p) => (p + 1) % PHASES.length)
    }, PHASE_MS)
    return () => window.clearInterval(id)
  }, [])

  const current = PHASES[phase]!

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-primary/20 bg-linear-to-br from-primary/[0.08] via-card to-muted/30 px-4 py-4 shadow-sm',
        className,
      )}
    >
      <style>{`
        @keyframes sanadi-breathe-ring-${uid} {
          0%, 100% { transform: scale(0.94); opacity: 0.75; }
          24% { transform: scale(1.14); opacity: 1; }
          25%, 49% { transform: scale(1.14); opacity: 1; }
          50% { transform: scale(1.14); opacity: 1; }
          74% { transform: scale(0.94); opacity: 0.85; }
          75%, 99% { transform: scale(0.94); opacity: 0.8; }
        }
        .sanadi-breathe-ring-${uid} {
          animation: sanadi-breathe-ring-${uid} 16s ease-in-out infinite;
        }
      `}</style>

      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full">
            <div
              className={cn('sanadi-breathe-ring-' + uid, 'absolute inset-0 rounded-full border-2 border-primary/45 bg-primary/10')}
              aria-hidden
            />
            <Wind className="relative z-[1] h-7 w-7 text-primary" aria-hidden />
          </div>
          <div className="min-w-0 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Sanadi suggests</p>
            <p className="text-sm font-semibold text-foreground">{current.title}</p>
            <p className="text-xs leading-relaxed text-muted-foreground">{current.hint}</p>
            <p className="text-[0.65rem] text-muted-foreground">Cycle repeats every ~16 seconds. Stop whenever you like.</p>
          </div>
        </div>
        <Button type="button" variant="ghost" size="sm" className="shrink-0 text-muted-foreground" onClick={onDismiss}>
          Not now
        </Button>
      </div>
    </div>
  )
}
