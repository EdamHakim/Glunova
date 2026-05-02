import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

import { NextResponse } from 'next/server'

export const runtime = 'nodejs'

/** Cache this file locally with `pnpm fetch-sanadi-avatar` when `models.readyplayer.me` is unreachable from Node */
const LOCAL_GL = join(process.cwd(), 'public', 'sanadi-local-avatar.glb')

const READY_PLAYER_ME_DEFAULT_GL =
  'https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?' +
  'morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown' +
  '&textureSizeLimit=1024&textureFormat=png'

async function serveLocalCached(): Promise<NextResponse | null> {
  try {
    const buf = await readFile(LOCAL_GL)
    return new NextResponse(buf, {
      status: 200,
      headers: {
        'Content-Type': 'model/gltf-binary',
        'Cache-Control': 'private, max-age=86400',
        'X-Sanadi-Avatar-Source': 'public/sanadi-local-avatar.glb',
      },
    })
  } catch {
    return null
  }
}

export async function GET() {
  const local = await serveLocalCached()
  if (local) return local

  try {
    const upstream = await fetch(READY_PLAYER_ME_DEFAULT_GL, {
      headers: {
        Accept: 'model/gltf-binary,*/*',
        'User-Agent': 'GlunovaSanadiTalkingHeadProxy/1.0',
      },
      next: { revalidate: 86_400 },
    })

    if (!upstream.ok) {
      const detail = `(Ready Player Me returned ${upstream.status})`
      return NextResponse.json(
        {
          error: 'Default avatar could not be loaded from CDN.',
          detail,
          hint: 'Run `pnpm fetch-sanadi-avatar` in `frontend/` once (internet), or add public/sanadi-local-avatar.glb manually.',
        },
        { status: 502 },
      )
    }

    const buffer = await upstream.arrayBuffer()
    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': 'model/gltf-binary',
        'Cache-Control': 'public, max-age=86400, s-maxage=86400',
        'X-Sanadi-Avatar-Source': 'upstream',
      },
    })
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    console.error('[api/sanadi-talkinghead-default]', message)
    const dnsBroken = message.includes('ENOTFOUND') || message.includes('getaddrinfo')
    return NextResponse.json(
      {
        error: 'Avatar unavailable: could not fetch from Ready Player Me and no local cache was found.',
        detail: dnsBroken
          ? 'DNS/network could not resolve models.readyplayer.me from the Next.js server.'
          : message.slice(0, 200),
        hint: 'Run `pnpm fetch-sanadi-avatar` in `frontend/` on a machine with internet once; it saves public/sanadi-local-avatar.glb. Or set NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB to another HTTPS or /public-relative .glb URL.',
      },
      { status: 503 },
    )
  }
}
