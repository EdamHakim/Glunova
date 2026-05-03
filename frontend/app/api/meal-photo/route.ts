import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

/** Free key: https://www.pexels.com/api/ — `PEXELS_API_KEY` in frontend/.env.local or backend/.env (monorepo). */
const PEXELS = 'https://api.pexels.com/v1/search'

function readPexelsKeyFromBackendEnv(): string | undefined {
  const candidates = [
    join(process.cwd(), '..', 'backend', '.env'),
    join(process.cwd(), 'backend', '.env'),
  ]
  let envPath: string | undefined
  for (const p of candidates) {
    if (existsSync(p)) {
      envPath = p
      break
    }
  }
  if (!envPath) return undefined
  try {
    for (const raw of readFileSync(envPath, 'utf8').split(/\r?\n/)) {
      const line = raw.trim()
      if (!line || line.startsWith('#')) continue
      const eq = line.indexOf('=')
      if (eq === -1) continue
      if (line.slice(0, eq).trim() !== 'PEXELS_API_KEY') continue
      let v = line.slice(eq + 1).trim()
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
        v = v.slice(1, -1)
      }
      return v.trim() || undefined
    }
  } catch {
    /* ignore */
  }
  return undefined
}

function resolvePexelsApiKey(): string | undefined {
  const fromNext = process.env.PEXELS_API_KEY?.trim()
  if (fromNext) return fromNext
  return readPexelsKeyFromBackendEnv()
}

type PexelsPhoto = {
  photographer?: string
  photographer_url?: string
  src?: { tiny?: string; small?: string; medium?: string; large?: string }
}

type PexelsSearch = { photos?: PexelsPhoto[] }

function thumbUrl(photo: PexelsPhoto | undefined): string | null {
  if (!photo?.src) return null
  const { src } = photo
  return src.small ?? src.medium ?? src.tiny ?? src.large ?? null
}

function searchQueriesFromMealName(raw: string): string[] {
  const q = raw.replace(/\s+/g, ' ').trim().slice(0, 120)
  const words = q.split(' ').filter(Boolean)
  const w4 = words.slice(0, 4).join(' ')
  const w2 = words.slice(0, 2).join(' ')
  const bases = [...new Set([q, w4, w2])].filter((s) => s.length >= 2)
  const out: string[] = []
  for (const b of bases) {
    out.push(`${b} food`)
    out.push(`${b} meal`)
  }
  return [...new Set(out)].slice(0, 5)
}

async function pexelsSearch(apiKey: string, searchText: string): Promise<PexelsPhoto | undefined> {
  const query = encodeURIComponent(searchText.slice(0, 120))
  const res = await fetch(`${PEXELS}?query=${query}&per_page=3`, {
    headers: { Authorization: apiKey },
    cache: 'no-store',
  })
  if (!res.ok) return undefined
  const data = (await res.json()) as PexelsSearch
  return data.photos?.[0]
}

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get('q')?.trim() ?? ''
  if (!q || q.length > 160) {
    return NextResponse.json({ url: null, error: 'invalid_query' }, { status: 400 })
  }

  const apiKey = resolvePexelsApiKey()
  if (!apiKey) {
    return NextResponse.json(
      { url: null, skipped: true },
      { headers: { 'Cache-Control': 'public, max-age=3600' } },
    )
  }

  try {
    let photo: PexelsPhoto | undefined
    for (const searchText of searchQueriesFromMealName(q)) {
      photo = await pexelsSearch(apiKey, searchText)
      if (photo) break
      await new Promise((r) => setTimeout(r, 55))
    }

    const url = thumbUrl(photo)
    return NextResponse.json(
      {
        url,
        credit: photo?.photographer ?? null,
        creditUrl: photo?.photographer_url ?? null,
      },
      { headers: { 'Cache-Control': 'public, max-age=86400' } },
    )
  } catch {
    return NextResponse.json({ url: null, error: 'fetch_failed' }, { status: 200 })
  }
}
