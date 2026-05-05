/**
 * GLBs under `frontend/public/3D Avatars/`.
 * Paths use `%20` for the directory name so fetches decode reliably everywhere.
 */

export const SANADI_AVATAR_PUBLIC_SEGMENT = '/3D%20Avatars'

/** Default companion mesh (full lip-sync visemes when model supports them). */
export const SANADI_DEFAULT_AVATAR_PATH = `${SANADI_AVATAR_PUBLIC_SEGMENT}/mpfb.glb`

export type SanadiAvatarChoice = {
  /** Stable id for telemetry / storage migration */
  id: string
  /** Short picker label */
  label: string
  /** Absolute same-origin URL under `public/` */
  path: string
}

function glb(label: string, file: string, id?: string): SanadiAvatarChoice {
  const base = id ?? file.replace(/\.glb$/i, '')
  return { id: base, label, path: `${SANADI_AVATAR_PUBLIC_SEGMENT}/${file}` }
}

/** Order is picker order — default listed first, then females, then males (alphabetical by label within groups). */
export const SANADI_AVATAR_CHOICES: SanadiAvatarChoice[] = [
  glb('Sanadi (default)', 'mpfb.glb', 'sanadi-default'),

  glb('Elena', 'female-elena.glb'),
  glb('Lina', 'female-lina.glb'),
  glb('Sara', 'female-sara.glb'),
  glb('Noor', 'female-noor.glb'),
  glb('Maya', 'female-maya.glb'),
  glb('Zara', 'female-zara.glb'),
  glb('Amel', 'female-amel.glb'),

  glb('Omar', 'male-omar.glb'),
  glb('Youssef', 'male-youssef.glb'),
  glb('Karim', 'male-karim.glb'),
  glb('Tarek', 'male-tarek.glb'),
  glb('Hakim', 'male-hakim.glb'),

  glb('Mehdi', 'male-mehdi.glb'),
  glb('Rashid', 'male-rashid.glb'),
  glb('Nabil', 'male-nabil.glb'),
  glb('Fares', 'male-fares.glb'),
]

const CHOICE_BY_FILENAME = new Map(SANADI_AVATAR_CHOICES.map((c) => [c.path.split('/').pop()!, c]))

/** Previous filenames (and older picker paths) → new URL so saved session prefs keep working after renames. */
const LEGACY_GLB_FILENAME: Record<string, string> = {
  'female 1.glb': 'female-elena.glb',
  'female 6.glb': 'female-noor.glb',
  'female 7.glb': 'female-maya.glb',
  'male 1.glb': 'male-omar.glb',
  'male 2.glb': 'male-youssef.glb',
  'male 3.glb': 'male-karim.glb',
  'male 4.glb': 'male-tarek.glb',
  'female-avatar1.glb': 'female-elena.glb',
  'female-avatar2.glb': 'female-lina.glb',
  'female-avatar3.glb': 'female-sara.glb',
  'female-avatar4.glb': 'female-zara.glb',
  'female-avatar5.glb': 'female-amel.glb',
  'male-avatar1.glb': 'male-hakim.glb',

  'male-avatar3.glb': 'male-mehdi.glb',
  'male-avatar4.glb': 'male-rashid.glb',
  'male-avatar5.glb': 'male-nabil.glb',
  'male-avatar6.glb': 'male-fares.glb',
  'avatar1.glb': 'female-elena.glb',
  'avatar2.glb': 'female-lina.glb',
  'avatar3.glb': 'female-sara.glb',
  'brunette.glb': 'female-zara.glb',
  'mpfbbb.glb': 'mpfb.glb',
  'p-f-a1.glb': 'female-amel.glb',
  'p-f-a2.glb': 'female-maya.glb',
  'professionalfemale.glb': 'female-sara.glb',
  'p-m-a3.glb': 'male-mehdi.glb',
  'p-m-a4.glb': 'male-karim.glb',
}

function resolveLegacyFilename(decodedBasename: string): string | null {
  return LEGACY_GLB_FILENAME[decodedBasename]
    ?? LEGACY_GLB_FILENAME[decodedBasename.toLowerCase()]
    ?? null
}

/** Derive avatar gender from its path — male-*.glb → "male", everything else → "female". */
export function sanadiAvatarGender(path: string): 'male' | 'female' {
  const filename = decodeURIComponent(path).split('/').pop() ?? ''
  return filename.startsWith('male-') ? 'male' : 'female'
}

export function coerceSanadiAvatarPath(raw: string | null): string {
  if (!raw?.trim()) return SANADI_DEFAULT_AVATAR_PATH
  const t = raw.trim()
  if (SANADI_AVATAR_CHOICES.some((c) => c.path === t)) return t
  if (t === '/mpfb.glb') return SANADI_DEFAULT_AVATAR_PATH

  let decoded = t
  try {
    decoded = decodeURI(t)
  } catch {
    /* keep t */
  }
  const m = decoded.match(/^\/3D\s+Avatars\/(.+\.glb)$/i)
  if (m) {
    let file = m[1]!
    try {
      file = decodeURIComponent(file)
    } catch {
      /* keep file */
    }
    const migrated = resolveLegacyFilename(file)
    const finalName = migrated ?? file
    const choice =
      CHOICE_BY_FILENAME.get(finalName)
      ?? CHOICE_BY_FILENAME.get(finalName.toLowerCase())
    if (choice) return choice.path
    const fallback = SANADI_AVATAR_CHOICES.find((c) =>
      c.path.toLowerCase().endsWith('/' + finalName.toLowerCase()))
    if (fallback) return fallback.path
  }
  return SANADI_DEFAULT_AVATAR_PATH
}
