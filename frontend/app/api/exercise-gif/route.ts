import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LocalExercise {
  id:             string
  name:           string
  category:       string
  primaryMuscles: string[]
  instructions:   string[]
  images:         string[]
}

export interface ExerciseGifResult {
  gifUrl:       string | null
  target:       string | null
  instructions: string[]
}

const EMPTY: ExerciseGifResult = { gifUrl: null, target: null, instructions: [] }

// Images are served from GitHub CDN — stable, no API key, no rate limits.
const GITHUB_BASE = 'https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/'

// ── Local dataset ─────────────────────────────────────────────────────────────

let _db: LocalExercise[] | null = null

function getDb(): LocalExercise[] {
  if (_db) return _db
  try {
    const p = join(process.cwd(), 'lib', 'data', 'exercises-db.json')
    _db = JSON.parse(readFileSync(p, 'utf8')) as LocalExercise[]
    console.log(`[exercise-gif] Loaded ${_db.length} exercises from bundled dataset`)
  } catch (e) {
    console.error('[exercise-gif] Failed to load exercises-db.json:', e)
    _db = []
  }
  return _db
}

// ── Category mapping ──────────────────────────────────────────────────────────

const TYPE_TO_CATEGORIES: Record<string, string[]> = {
  cardio:      ['cardio', 'plyometrics'],
  strength:    ['strength', 'powerlifting', 'olympic_weightlifting', 'weighted_bodyweight', 'strongman'],
  hiit:        ['plyometrics', 'cardio', 'crossfit'],
  flexibility: ['stretching'],
  mobility:    ['stretching'],
}

// ── Result cache ──────────────────────────────────────────────────────────────

const cache = new Map<string, ExerciseGifResult>()

// ── Name-similarity matching ──────────────────────────────────────────────────

// Below this threshold the match is considered unreliable — return null so the
// YouTube fallback is shown instead of a wrong exercise image.
const MIN_SCORE = 0.25

function words(s: string): string[] {
  return s.toLowerCase().replace(/[^a-z\s]/g, ' ').split(/\s+/).filter(w => w.length > 2)
}

function score(dbName: string, query: string): number {
  const dw = words(dbName)
  const qw = new Set(words(query))
  if (!dw.length || !qw.size) return 0
  let hits = 0
  for (const w of dw) {
    if (qw.has(w)) hits += 2
    else for (const q of qw) if (w.includes(q) || q.includes(w)) hits += 1
  }
  return hits / (dw.length + qw.size)
}

function bestMatch(pool: LocalExercise[], name: string): [LocalExercise | null, number] {
  let best: LocalExercise | null = null
  let bestScore = -1
  for (const ex of pool) {
    const s = score(ex.name, name)
    if (s > bestScore) { bestScore = s; best = ex }
  }
  return [best, bestScore]
}

function toResult(ex: LocalExercise): ExerciseGifResult {
  return {
    gifUrl:       GITHUB_BASE + ex.images[0],
    target:       ex.primaryMuscles?.[0] ?? null,
    instructions: ex.instructions?.slice(0, 5) ?? [],
  }
}

function resolve(name: string, type: string): ExerciseGifResult | null {
  const all = getDb()
  const typeKey = type.trim().toLowerCase()
  const cats = new Set(TYPE_TO_CATEGORIES[typeKey] ?? [])
  const pool = cats.size > 0 ? all.filter(e => cats.has(e.category)) : all

  const [best, bestScore] = bestMatch(pool.length > 0 ? pool : all, name)

  // Confident match within the category pool — use it.
  if (best && bestScore >= MIN_SCORE && best.images?.length) return toResult(best)

  // Poor match in category pool — widen search to the whole dataset.
  if (pool.length > 0 && pool.length < all.length) {
    const [globalBest, globalScore] = bestMatch(all, name)
    if (globalBest && globalScore >= MIN_SCORE && globalBest.images?.length) return toResult(globalBest)
  }

  // No confident match anywhere → let the frontend show the YouTube fallback.
  return null
}

// ── Handler ───────────────────────────────────────────────────────────────────

export async function GET(req: NextRequest): Promise<NextResponse> {
  const name = req.nextUrl.searchParams.get('q')?.trim()    ?? ''
  const type = req.nextUrl.searchParams.get('type')?.trim() ?? ''

  if (!name) return NextResponse.json(EMPTY)

  const key = `${name}|${type}`
  const hit = cache.get(key)
  if (hit) return NextResponse.json(hit, { headers: { 'Cache-Control': 'public, max-age=86400' } })

  const result = resolve(name, type) ?? EMPTY
  cache.set(key, result)

  console.log(`[exercise-gif] "${name}" (${type}) → ${result.gifUrl ? '✓' : 'null'}`)
  return NextResponse.json(result, { headers: { 'Cache-Control': 'public, max-age=86400' } })
}
