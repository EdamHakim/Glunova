/**
 * Populate `public/sanadi-local-avatar.glb` for TalkingHead when Node cannot reach Ready Player Me.
 *
 * From `frontend/`:
 *   `pnpm fetch-sanadi-avatar`          — HTTP fetch (needs DNS for the mirror URL).
 *   `pnpm fetch-sanadi-avatar -- ./Downloads/file.glb` — copy an existing GLB (e.g. saved from browser).
 *
 * Override URL: env `SANADI_AVATAR_FETCH_URL=https://...` is tried before the default RPM URL.
 */

import { copyFile, mkdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const rootDir = join(__dirname, '..')
const outPath = join(rootDir, 'public', 'sanadi-local-avatar.glb')

const READY_PLAYER_ME_DEFAULT_GL =
  'https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?' +
  'morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown' +
  '&textureSizeLimit=1024&textureFormat=png'

/** Node/undici often wrap DNS errors on `error.cause`. */
function looksLikeDnsFailure(e) {
  if (!(e instanceof Error)) return false
  if (/ENOTFOUND|EAI_AGAIN|getaddrinfo/i.test(e.message)) return true
  const c = /** @type {{ message?: string; code?: string }} | undefined */ (e.cause)
  if (!c) return false
  if (typeof c.message === 'string' && /ENOTFOUND|getaddrinfo/i.test(c.message)) return true
  return c.code === 'ENOTFOUND' || c.code === 'EAI_AGAIN'
}

async function saveFromMirror(url, label) {
  const res = await fetch(url, {
    redirect: 'follow',
    headers: {
      Accept: 'model/gltf-binary,*/*',
      'User-Agent': 'GlunovaSanadiFetcher/1.0',
    },
  })
  if (!res.ok) {
    throw new Error(`${label}: HTTP ${res.status} ${res.statusText}`)
  }
  const buf = new Uint8Array(await res.arrayBuffer())
  if (buf.byteLength < 4096) {
    throw new Error(`${label}: response too small (${buf.byteLength}b), likely HTML error`)
  }
  await mkdir(dirname(outPath), { recursive: true })
  await writeFile(outPath, buf)
  return buf.byteLength
}

function printENOTFOUNDHelp() {
  console.error('')
  console.error('Node could not resolve the hostname (ENOTFOUND). Your network/DNS/firewall blocks that domain.')
  console.error('')
  console.error('Options:')
  console.error(
    '  1) Use another connection (mobile hotspot/VPN/DNS such as 1.1.1.1) and run: pnpm fetch-sanadi-avatar',
  )
  console.error(
    `  2) On ANY device browser, open:\n      ${READY_PLAYER_ME_DEFAULT_GL}\n     Save the file, then:`,
  )
  console.error('       pnpm fetch-sanadi-avatar -- ".\\path\\to\\saved-file.glb"')
  console.error('  3) Put any TalkingHead-ready .glb under public/ and set NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB=/filename.glb')
  console.error('  4) Set SANADI_AVATAR_FETCH_URL to a reachable mirror (HTTPS), then run pnpm fetch-sanadi-avatar again.')
  console.error(
    '  5) Without any GLB download: the dev server can still serve `public/mpfb.glb` as a last resort via `/api/sanadi-talkinghead-default`, or set NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB=/mpfb.glb (lip sync is limited on that mesh).',
  )
  console.error('')
}

async function main() {
  const args = process.argv.slice(2)
  const positional = args.find((a) => !a.startsWith('-'))

  if (positional) {
    const src = resolve(process.cwd(), positional)
    if (!existsSync(src)) {
      console.error(`Not found (copy mode): ${src}`)
      process.exit(1)
    }
    await mkdir(dirname(outPath), { recursive: true })
    await copyFile(src, outPath)
    console.info(`Copied → ${outPath}`)
    return
  }

  const mirrors = []
  const envUrl = typeof process.env.SANADI_AVATAR_FETCH_URL === 'string' ? process.env.SANADI_AVATAR_FETCH_URL.trim() : ''
  if (envUrl) mirrors.push({ url: envUrl, label: 'SANADI_AVATAR_FETCH_URL' })
  mirrors.push({ url: READY_PLAYER_ME_DEFAULT_GL, label: 'Ready Player Me default' })

  let lastErr = ''
  let sawENOTFOUND = false

  for (const { url, label } of mirrors) {
    try {
      const n = await saveFromMirror(url, label)
      console.info(`Saved ${n} bytes → ${outPath}\n(Source: ${label})`)
      return
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn(`${label}: ${msg}`)
      lastErr = msg
      if (looksLikeDnsFailure(e)) sawENOTFOUND = true
    }
  }

  console.error('')
  console.error('All mirror attempts failed.')
  if (sawENOTFOUND) printENOTFOUNDHelp()
  else {
    console.error(
      'Or copy a `.glb` you already have:\n  pnpm fetch-sanadi-avatar -- ".\\Downloads\\saved-file.glb"',
    )
    console.error('')
  }
  process.exit(1)
}

await main()
