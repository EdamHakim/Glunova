'use client'

import { useEffect, useState } from 'react'
import { ChefHat } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

// ── Shared fetch infrastructure ───────────────────────────────────────────────

type PhotoResult = { url: string | null; credit: string | null; creditUrl: string | null }

const cache    = new Map<string, PhotoResult>()
const inflight = new Map<string, Promise<PhotoResult>>()

const MAX_CONCURRENT = 5
let active = 0
const waitQueue: Array<() => void> = []

function acquire(): Promise<void> {
  if (active < MAX_CONCURRENT) { active++; return Promise.resolve() }
  return new Promise(resolve => waitQueue.push(() => { active++; resolve() }))
}

function release() {
  active--
  waitQueue.shift()?.()
}

export async function loadMealPhoto(name: string): Promise<PhotoResult> {
  const hit = cache.get(name)
  if (hit) return hit
  const pending = inflight.get(name)
  if (pending) return pending

  const p = (async (): Promise<PhotoResult> => {
    await acquire()
    try {
      const r = await fetch(`/api/meal-photo?q=${encodeURIComponent(name)}`)
      const d = await r.json() as Partial<PhotoResult>
      return { url: d.url ?? null, credit: d.credit ?? null, creditUrl: d.creditUrl ?? null }
    } catch {
      return { url: null, credit: null, creditUrl: null }
    } finally {
      release()
      inflight.delete(name)
    }
  })()

  inflight.set(name, p)
  const result = await p
  cache.set(name, result)
  return result
}

// ── MealPhoto component ───────────────────────────────────────────────────────

export function MealPhoto({ name }: { name: string }) {
  const [url, setUrl]             = useState<string | null | undefined>(undefined)
  const [credit, setCredit]       = useState<string | null>(null)
  const [creditUrl, setCreditUrl] = useState<string | null>(null)
  const [broken, setBroken]       = useState(false)

  useEffect(() => {
    let cancelled = false
    setUrl(undefined); setCredit(null); setCreditUrl(null); setBroken(false)
    loadMealPhoto(name).then(d => {
      if (!cancelled) { setUrl(d.url); setCredit(d.credit); setCreditUrl(d.creditUrl) }
    })
    return () => { cancelled = true }
  }, [name])

  const showImg = url && !broken

  return (
    <div className="relative h-24 w-full shrink-0 overflow-hidden rounded-md bg-muted">
      {url === undefined ? (
        <Skeleton className="absolute inset-0 h-full w-full rounded-md" />
      ) : showImg ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
            decoding="async"
            sizes="220px"
            onError={() => setBroken(true)}
          />
          {(credit || creditUrl) && (
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-2 pb-1 pt-4">
              {creditUrl ? (
                <a href={creditUrl} target="_blank" rel="noopener noreferrer"
                  className="text-[10px] text-white/90 hover:underline">
                  {credit ?? 'Photo'} · Pexels
                </a>
              ) : (
                <span className="text-[10px] text-white/80">Pexels</span>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="flex h-full w-full items-center justify-center text-muted-foreground">
          <ChefHat className="h-10 w-10 opacity-35" aria-hidden />
        </div>
      )}
    </div>
  )
}
