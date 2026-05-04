'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronDown, Dumbbell, ListOrdered, Youtube } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import type { ExerciseGifResult } from '@/app/api/exercise-gif/route'

// ── Client-side cache ─────────────────────────────────────────────────────────

const gifCache = new Map<string, ExerciseGifResult>()

async function fetchGif(name: string, exerciseType: string): Promise<ExerciseGifResult> {
  const key = `${name}|${exerciseType}`
  if (gifCache.has(key)) return gifCache.get(key)!
  try {
    const r = await fetch(
      `/api/exercise-gif?q=${encodeURIComponent(name)}&type=${encodeURIComponent(exerciseType)}`,
    )
    const d: ExerciseGifResult = await r.json()
    gifCache.set(key, d)
    return d
  } catch {
    return { gifUrl: null, target: null, instructions: [] }
  }
}

// ── Animated two-frame preview ────────────────────────────────────────────────
// free-exercise-db images come in pairs: /0.jpg (start) and /1.jpg (end).
// We swap between them every 800 ms to simulate motion.

function AnimatedExerciseImage({ baseUrl, name }: { baseUrl: string; name: string }) {
  const [frame, setFrame]     = useState(0)
  const [broken, setBroken]   = useState(false)

  // Derive the two frame URLs — replace /0.jpg with /1.jpg for the second frame.
  const frame0 = baseUrl
  const frame1 = baseUrl.replace(/\/0\.jpg$/, '/1.jpg')
  const hasTwoFrames = frame1 !== frame0

  useEffect(() => {
    if (!hasTwoFrames) return
    const id = setInterval(() => setFrame(f => (f === 0 ? 1 : 0)), 800)
    return () => clearInterval(id)
  }, [hasTwoFrames])

  if (broken) return null

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={frame === 0 ? frame0 : frame1}
      alt={name}
      className="h-full w-full object-contain transition-opacity duration-300"
      onError={() => setBroken(true)}
    />
  )
}

// ── ExerciseGif ───────────────────────────────────────────────────────────────

export function ExerciseGif({
  name,
  exerciseType,
}: {
  name: string
  exerciseType: string
}) {
  const [data, setData]         = useState<ExerciseGifResult | null>(null)
  const [imgBroken, setImgBroken] = useState(false)
  const [stepsOpen, setStepsOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setImgBroken(false)
    fetchGif(name, exerciseType).then(d => { if (!cancelled) setData(d) })
    return () => { cancelled = true }
  }, [name, exerciseType])

  const showImage = data?.gifUrl && !imgBroken
  const youtubeUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(name + ' exercise how to')}`

  return (
    <div className="space-y-2">
      {/* Exercise image / fallback */}
      <div className="relative h-44 w-full overflow-hidden rounded-lg bg-muted flex items-center justify-center">
        {data === null ? (
          <Skeleton className="absolute inset-0 h-full w-full" />
        ) : showImage ? (
          <>
            <AnimatedExerciseImage
              baseUrl={data.gifUrl!}
              name={name}
            />
            {data.target && (
              <div className="absolute bottom-2 left-2">
                <Badge className="text-[10px] bg-black/60 text-white border-0 hover:bg-black/60 capitalize">
                  {data.target}
                </Badge>
              </div>
            )}
            <a
              href={youtubeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute top-2 right-2 p-1 rounded-md bg-black/50 text-white/70 hover:text-red-400 hover:bg-black/70 transition-colors"
              title="Watch on YouTube"
            >
              <Youtube className="h-3.5 w-3.5" />
            </a>
          </>
        ) : (
          /* No image found — link directly to YouTube */
          <a
            href={youtubeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-col items-center gap-2.5 text-muted-foreground/50 hover:text-red-500 transition-colors group"
          >
            <Youtube className="h-11 w-11" />
            <span className="text-[11px] font-medium group-hover:underline">Watch on YouTube</span>
          </a>
        )}
      </div>

      {/* Step-by-step instructions collapsible */}
      {data?.instructions && data.instructions.length > 0 && (
        <Collapsible open={stepsOpen} onOpenChange={setStepsOpen}>
          <CollapsibleTrigger className="flex items-center gap-1.5 text-xs text-primary hover:underline">
            <ListOrdered className="h-3.5 w-3.5" />
            How to perform
            <ChevronDown className={`h-3 w-3 transition-transform ${stepsOpen ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ol className="mt-2 space-y-1.5">
              {data.instructions.map((step, i) => (
                <li key={i} className="flex gap-2 text-xs text-muted-foreground leading-snug">
                  <span className="font-bold text-primary shrink-0 mt-px">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}

// ── SetTracker ────────────────────────────────────────────────────────────────

export function SetTracker({
  sets,
  reps,
}: {
  sets: number
  reps?: number | null
}) {
  const [completed, setCompleted] = useState<boolean[]>(() => Array(sets).fill(false))

  const doneCount = completed.filter(Boolean).length
  const allDone   = doneCount === sets && sets > 0

  const toggle = (i: number) =>
    setCompleted(prev => prev.map((v, j) => (j === i ? !v : v)))

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">
          {reps ? `${reps} reps × ${sets} sets` : `${sets} sets`}
        </span>
        <span className={`font-semibold tabular-nums ${allDone ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}>
          {doneCount} / {sets}
        </span>
      </div>

      <div className="flex gap-2 flex-wrap">
        {completed.map((done, i) => (
          <button
            key={i}
            onClick={() => toggle(i)}
            className={`h-9 w-9 rounded-lg text-xs font-bold transition-all border-2 select-none ${
              done
                ? 'bg-green-500 border-green-500 text-white shadow-sm scale-95'
                : 'border-border bg-background hover:border-primary/60 text-muted-foreground hover:text-foreground'
            }`}
          >
            {done ? '✓' : i + 1}
          </button>
        ))}
      </div>

      {allDone && (
        <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span className="text-xs font-semibold">All sets done!</span>
        </div>
      )}
    </div>
  )
}
