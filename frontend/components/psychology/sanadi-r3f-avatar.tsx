'use client'

import {
  Component,
  forwardRef,
  Suspense,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'
import { cn } from '@/lib/utils'
import type { AvatarEmotion, AvatarPhase } from '@/components/psychology/sanadi-avatar'
import type { SynthesizedSpeech } from '@/lib/psychology-api'

// ─── Exported types (identical to sanadi-talkinghead) ────────────────────────

export type PsychologyTtsLang = 'en' | 'fr' | 'ar' | 'darija' | 'mixed'

export type SanadiTalkingHeadHandle = {
  speakFromServiceTts: (
    speech: SynthesizedSpeech,
    replyText: string,
    lang: PsychologyTtsLang,
    onEnded: () => void,
  ) => Promise<boolean>
  interruptSpeech: () => void
  isAvatarReady: () => boolean
}

type Props = {
  active: boolean
  phase: AvatarPhase
  emotion: AvatarEmotion | null | undefined
  distressScore?: number | null
  variant?: 'inline' | 'overlay' | 'voiceHero'
  className?: string
  onAssistantAnalyser?: (node: AnalyserNode | null) => void
}

// ─── Oculus viseme system ─────────────────────────────────────────────────────

const OCULUS_VISEMES = [
  'viseme_sil', 'viseme_PP', 'viseme_FF', 'viseme_TH', 'viseme_DD',
  'viseme_kk',  'viseme_CH', 'viseme_SS', 'viseme_nn', 'viseme_RR',
  'viseme_aa',  'viseme_E',  'viseme_I',  'viseme_O',  'viseme_U',
] as const
type OcViseme = (typeof OCULUS_VISEMES)[number]

/** Jaw-open weight per viseme (0–1). Drives jawOpen ARKit morph. */
const VISEME_JAW: Record<OcViseme, number> = {
  viseme_sil: 0,    viseme_PP: 0.05, viseme_FF: 0.12, viseme_TH: 0.18,
  viseme_DD:  0.22, viseme_kk: 0.18, viseme_CH: 0.26, viseme_SS: 0.12,
  viseme_nn:  0.08, viseme_RR: 0.22, viseme_aa: 0.65, viseme_E:  0.38,
  viseme_I:   0.28, viseme_O:  0.48, viseme_U:  0.34,
}

// Digraph → viseme (checked before monograph)
const DIGRAPH: Record<string, OcViseme> = {
  th: 'viseme_TH', ch: 'viseme_CH', sh: 'viseme_CH',
  ph: 'viseme_FF', wh: 'viseme_U',  ng: 'viseme_kk', gh: 'viseme_sil',
}
// Single char → viseme
const MONO: Record<string, OcViseme> = {
  a: 'viseme_aa', e: 'viseme_E',  i: 'viseme_I',  o: 'viseme_O',  u: 'viseme_U',
  p: 'viseme_PP', b: 'viseme_PP', m: 'viseme_PP',
  f: 'viseme_FF', v: 'viseme_FF',
  d: 'viseme_DD', t: 'viseme_DD', l: 'viseme_DD',
  n: 'viseme_nn',
  k: 'viseme_kk', g: 'viseme_kk', c: 'viseme_kk', q: 'viseme_kk',
  s: 'viseme_SS', z: 'viseme_SS', x: 'viseme_SS',
  j: 'viseme_CH',
  r: 'viseme_RR',
  w: 'viseme_U',  y: 'viseme_I',  h: 'viseme_sil',
}

function wordToVisemes(word: string): OcViseme[] {
  let s = word.toLowerCase().replace(/[^a-z]/g, '')
  const out: OcViseme[] = []
  while (s.length) {
    const di = DIGRAPH[s.slice(0, 2)]
    if (di) { out.push(di); s = s.slice(2); continue }
    const mo = MONO[s[0]!]
    if (mo) out.push(mo)
    s = s.slice(1)
  }
  return out
}

type VisemeSeg = { startMs: number; endMs: number; viseme: OcViseme }

function buildSegments(words: string[], wtimes: number[], wdurations: number[]): VisemeSeg[] {
  const segs: VisemeSeg[] = []
  let cursor = 0
  for (let wi = 0; wi < words.length; wi++) {
    const wStart = wtimes[wi]!
    const wDur   = wdurations[wi]!
    if (wStart > cursor) segs.push({ startMs: cursor, endMs: wStart, viseme: 'viseme_sil' })
    const ph = wordToVisemes(words[wi]!)
    if (!ph.length) {
      segs.push({ startMs: wStart, endMs: wStart + wDur, viseme: 'viseme_sil' })
    } else {
      const pDur = wDur / ph.length
      ph.forEach((v, pi) => segs.push({ startMs: wStart + pi * pDur, endMs: wStart + (pi + 1) * pDur, viseme: v }))
    }
    cursor = wStart + wDur
  }
  segs.push({ startMs: cursor, endMs: Infinity, viseme: 'viseme_sil' })
  return segs
}

function buildSegmentsFromText(text: string, durationMs: number): VisemeSeg[] {
  const words = text.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return [{ startMs: 0, endMs: Infinity, viseme: 'viseme_sil' }]
  const weights = words.map(w => Math.max(1, w.replace(/\W/g, '').length))
  const total   = weights.reduce((a, b) => a + b, 0)
  const wdurs   = weights.map(w => (w / total) * durationMs)
  const wtimes: number[] = []
  let acc = 0; for (const d of wdurs) { wtimes.push(acc); acc += d }
  return buildSegments(words, wtimes, wdurs)
}

// ─── Bridges (mutable refs shared outer ↔ inner without prop churn) ──────────

type AudioBridge = {
  analyser:              AnalyserNode | null
  isSpeaking:           boolean
  audioCtx:             AudioContext | null
  playbackStartCtxTime: number
  visemeSegments:       VisemeSeg[]
  speechId:             number      // increments each new utterance → resets cursor
}

type StateBridge = { phase: AvatarPhase; emotion: AvatarEmotion | null }

// ─── ARKit morph name constants ───────────────────────────────────────────────

const M_JAW       = 'jawOpen'
const M_FUNNEL    = 'mouthFunnel'
const M_PUCKER    = 'mouthPucker'
const M_BLINK_L   = 'eyeBlinkLeft'
const M_BLINK_R   = 'eyeBlinkRight'
const M_SMILE_L   = 'mouthSmileLeft'
const M_SMILE_R   = 'mouthSmileRight'
const M_FROWN_L   = 'mouthFrownLeft'
const M_FROWN_R   = 'mouthFrownRight'
const M_BROW_UP_L = 'browOuterUpLeft'
const M_BROW_UP_R = 'browOuterUpRight'
const M_BROW_DN_L = 'browDownLeft'
const M_BROW_DN_R = 'browDownRight'
const M_BROW_INN  = 'browInnerUp'

const EMOTION_MORPHS: Record<NonNullable<AvatarEmotion>, Partial<Record<string, number>>> = {
  neutral:   {},
  happy:     { [M_SMILE_L]: 0.45, [M_SMILE_R]: 0.45, [M_BROW_UP_L]: 0.15, [M_BROW_UP_R]: 0.15 },
  anxious:   { [M_BROW_INN]: 0.35, [M_BROW_UP_L]: 0.20, [M_BROW_UP_R]: 0.20 },
  distressed:{ [M_BROW_DN_L]: 0.35, [M_BROW_DN_R]: 0.35, [M_FROWN_L]: 0.25, [M_FROWN_R]: 0.25, [M_BROW_INN]: 0.20 },
  depressed: { [M_BROW_DN_L]: 0.20, [M_BROW_DN_R]: 0.20, [M_FROWN_L]: 0.20, [M_FROWN_R]: 0.20 },
}
const EMOTION_KEYS = [M_SMILE_L, M_SMILE_R, M_FROWN_L, M_FROWN_R,
                      M_BROW_UP_L, M_BROW_UP_R, M_BROW_DN_L, M_BROW_DN_R, M_BROW_INN]

// ─── Bone discovery ───────────────────────────────────────────────────────────

type BoneMap = {
  head: THREE.Bone|null; neck: THREE.Bone|null
  spine: THREE.Bone|null; chest: THREE.Bone|null
  leftEye: THREE.Bone|null; rightEye: THREE.Bone|null
  leftArm: THREE.Bone|null; rightArm: THREE.Bone|null
  leftFore: THREE.Bone|null; rightFore: THREE.Bone|null
}
const emptyBones = (): BoneMap => ({
  head:null, neck:null, spine:null, chest:null,
  leftEye:null, rightEye:null,
  leftArm:null, rightArm:null, leftFore:null, rightFore:null,
})

function discoverBones(root: THREE.Object3D): BoneMap {
  const b = emptyBones()
  root.traverse((n) => {
    if (!(n instanceof THREE.Bone)) return
    const lo = n.name.toLowerCase()
    if (!b.head     && /^head$/i.test(n.name)) b.head = n
    if (!b.neck     && /neck/i.test(lo) && !/tie/i.test(lo)) b.neck = n
    if (!b.spine    && /^(spine|spine\.?001)$/i.test(n.name)) b.spine = n
    if (!b.chest    && /(spine[12]|spine\.?00[23]|chest|thorax)/i.test(lo)) b.chest = n
    if (!b.leftEye  && /(left.?eye|eye.*left|eye\.?l$)/i.test(lo)) b.leftEye = n
    if (!b.rightEye && /(right.?eye|eye.*right|eye\.?r$)/i.test(lo)) b.rightEye = n
    if (!b.leftArm  && /(left.*arm|upper.?arm.*\.l)/i.test(lo) && !/fore/i.test(lo)) b.leftArm = n
    if (!b.rightArm && /(right.*arm|upper.?arm.*\.r)/i.test(lo) && !/fore/i.test(lo)) b.rightArm = n
    if (!b.leftFore && /(left.*fore|fore.*left|forearm.*\.l)/i.test(lo)) b.leftFore = n
    if (!b.rightFore && /(right.*fore|fore.*right|forearm.*\.r)/i.test(lo)) b.rightFore = n
  })
  return b
}

// ─── Error boundary ───────────────────────────────────────────────────────────

class AvatarErrorBoundary extends Component<
  { children: ReactNode; onError: (m: string) => void },
  { failed: boolean }
> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(e: Error) { this.props.onError(e.message) }
  render() { return this.state.failed ? null : this.props.children }
}

// ─── R3F scene ────────────────────────────────────────────────────────────────

type SceneProps = {
  audioRef: MutableRefObject<AudioBridge>
  stateRef: MutableRefObject<StateBridge>
  glbUrl: string
  onLoad: () => void
}

function AvatarScene({ audioRef, stateRef, glbUrl, onLoad }: SceneProps) {
  const { scene } = useGLTF(glbUrl)

  const meshesRef      = useRef<THREE.Mesh[]>([])
  const bonesRef       = useRef<BoneMap>(emptyBones())
  const baseRotsRef    = useRef<Map<THREE.Bone, THREE.Euler>>(new Map())
  const hasOcVisemsRef = useRef(false)

  // Pre-allocated audio buffers (avoids GC pressure at 60 fps)
  const tdBuf = useRef(new Float32Array(512))

  useEffect(() => {
    const meshes: THREE.Mesh[] = []
    let hasOc = false
    scene.traverse((node) => {
      if (node instanceof THREE.Mesh && node.morphTargetDictionary && node.morphTargetInfluences) {
        node.morphTargetInfluences.fill(0)
        meshes.push(node)
        if (!hasOc) hasOc = Object.keys(node.morphTargetDictionary).some(k => k.startsWith('viseme_'))
      }
    })
    meshesRef.current = meshes
    hasOcVisemsRef.current = hasOc

    const bones = discoverBones(scene)
    bonesRef.current = bones
    const rots = new Map<THREE.Bone, THREE.Euler>()
    for (const bone of Object.values(bones)) { if (bone) rots.set(bone, bone.rotation.clone()) }
    baseRotsRef.current = rots

    onLoad()
  }, [scene, onLoad])

  // Per-frame animation refs
  const smoothJaw     = useRef(0)
  const visemeCursor  = useRef(0)
  const prevSpeechId  = useRef(-1)
  const speechEnv     = useRef(0)   // slow-smoothed amplitude → body reactions
  const blinkTimer    = useRef(Math.random() * 3)
  const blinkPhase    = useRef(0)
  const eyeTimer      = useRef(3 + Math.random() * 3)
  const eyeState      = useRef<'camera'|'away'>('camera')
  const eyeTargH      = useRef(0)
  const eyeTargV      = useRef(0)
  const eyeCurrH      = useRef(0)
  const eyeCurrV      = useRef(0)
  const timeAcc       = useRef(0)
  const gSeed         = useRef(Math.random() * Math.PI * 2)

  useFrame((_, dt) => {
    timeAcc.current += dt
    const t   = timeAcc.current
    const gp  = gSeed.current
    const ab  = audioRef.current
    const sb  = stateRef.current
    const meshes   = meshesRef.current
    const bones    = bonesRef.current
    const baseRots = baseRotsRef.current

    // ── Reset viseme cursor on new utterance ──────────────────────────
    if (ab.speechId !== prevSpeechId.current) {
      prevSpeechId.current = ab.speechId
      visemeCursor.current = 0
    }

    // ── Amplitude (RMS) ───────────────────────────────────────────────
    let amp = 0
    if (ab.analyser && ab.isSpeaking) {
      ab.analyser.getFloatTimeDomainData(tdBuf.current)
      let sum = 0
      for (let i = 0; i < tdBuf.current.length; i++) { const s = tdBuf.current[i]!; sum += s * s }
      const rms = Math.sqrt(sum / tdBuf.current.length)
      if (rms > 0.015) amp = Math.min(1, Math.pow((rms - 0.015) / 0.235, 0.65))
    }

    // ── Active viseme from timeline ───────────────────────────────────
    let activeV: OcViseme = 'viseme_sil'
    if (ab.isSpeaking && ab.audioCtx && ab.visemeSegments.length > 0) {
      const elapsedMs = Math.max(0, (ab.audioCtx.currentTime - ab.playbackStartCtxTime) * 1000)
      const segs = ab.visemeSegments
      while (visemeCursor.current < segs.length - 1) {
        if (elapsedMs >= (segs[visemeCursor.current + 1]?.startMs ?? Infinity))
          visemeCursor.current++
        else break
      }
      activeV = segs[visemeCursor.current]?.viseme ?? 'viseme_sil'
    }

    // Viseme intensity: amplitude envelope + minimum floor when in an active word
    const visemeInt = activeV === 'viseme_sil' ? 0 : Math.max(amp * 1.35, 0.22)

    // Jaw: viseme-driven when Oculus morphs available, amplitude-only fallback
    const jawTarget = hasOcVisemsRef.current
      ? (VISEME_JAW[activeV] ?? 0) * visemeInt
      : amp * 0.38
    smoothJaw.current = THREE.MathUtils.lerp(smoothJaw.current, ab.isSpeaking ? jawTarget : 0, ab.isSpeaking ? 0.30 : 0.06)
    const jaw = smoothJaw.current

    // Body envelope — much slower, drives head/arm reactions
    speechEnv.current = THREE.MathUtils.lerp(speechEnv.current, amp, 0.055)
    const bEnv = speechEnv.current
    const isSpeaking = ab.isSpeaking

    // ── Blink ─────────────────────────────────────────────────────────
    blinkTimer.current += dt
    if (blinkTimer.current >= 3.6 + Math.sin(t * 0.29) * 1.2) {
      blinkTimer.current = 0; blinkPhase.current = 1
    }
    let blinkV = 0
    if (blinkPhase.current > 0) {
      blinkPhase.current = Math.max(0, blinkPhase.current - dt * 10)
      blinkV = blinkPhase.current
    }

    // ── Eye state machine ─────────────────────────────────────────────
    eyeTimer.current -= dt
    if (eyeTimer.current <= 0) {
      if (eyeState.current === 'camera') {
        eyeState.current = 'away'
        eyeTimer.current = 0.25 + Math.random() * 0.55
        eyeTargH.current = (Math.random() - 0.5) * 0.32
        eyeTargV.current = -Math.random() * 0.10
        if (blinkPhase.current <= 0) blinkPhase.current = 1   // blink on look-away
      } else {
        eyeState.current = 'camera'
        eyeTargH.current = 0; eyeTargV.current = 0
        // Less frequent look-away when speaking (more eye contact), more when thinking
        eyeTimer.current = sb.phase === 'thinking'
          ? 1.2 + Math.random() * 2.0
          : sb.phase === 'speaking'
            ? 5.0 + Math.random() * 5.0
            : 2.5 + Math.random() * 3.5
      }
    }
    eyeCurrH.current = THREE.MathUtils.lerp(eyeCurrH.current, eyeTargH.current, 0.07)
    eyeCurrV.current = THREE.MathUtils.lerp(eyeCurrV.current, eyeTargV.current, 0.07)

    // ── Emotion morphs ────────────────────────────────────────────────
    const emotMorphs = EMOTION_MORPHS[sb.emotion ?? 'neutral'] ?? {}

    // ── Apply to all morph meshes ─────────────────────────────────────
    for (const mesh of meshes) {
      const dict = mesh.morphTargetDictionary!
      const inf  = mesh.morphTargetInfluences!

      // Oculus visemes
      if (hasOcVisemsRef.current) {
        for (const v of OCULUS_VISEMES) {
          const idx = dict[v]; if (idx === undefined) continue
          const tgt = (v === activeV && v !== 'viseme_sil') ? visemeInt : 0
          inf[idx] = THREE.MathUtils.lerp(inf[idx]!, tgt, 0.28)
        }
      }

      // Jaw
      const ji = dict[M_JAW]; if (ji !== undefined) inf[ji] = jaw

      // Mouth shape from viseme
      const isOU = activeV === 'viseme_O' || activeV === 'viseme_U'
      const fi = dict[M_FUNNEL]
      if (fi !== undefined)
        inf[fi] = THREE.MathUtils.lerp(inf[fi]!, isSpeaking ? (isOU ? jaw * 0.55 : jaw * 0.18) : 0, 0.22)
      const pi = dict[M_PUCKER]
      if (pi !== undefined)
        inf[pi] = THREE.MathUtils.lerp(inf[pi]!, isSpeaking && activeV === 'viseme_U' ? jaw * 0.65 : 0, 0.22)

      // Blink
      const bli = dict[M_BLINK_L]; if (bli !== undefined) inf[bli] = blinkV
      const bri = dict[M_BLINK_R]; if (bri !== undefined) inf[bri] = blinkV

      // Emotion expression — very slow lerp for natural transitions
      for (const key of EMOTION_KEYS) {
        const idx = dict[key]; if (idx === undefined) continue
        inf[idx] = THREE.MathUtils.lerp(inf[idx]!, emotMorphs[key] ?? 0, 0.018)
      }
    }

    // ── Eye bones ─────────────────────────────────────────────────────
    const applyEye = (bone: THREE.Bone | null) => {
      if (!bone) return
      const base = baseRots.get(bone)
      bone.rotation.y = THREE.MathUtils.lerp(bone.rotation.y, (base?.y ?? 0) + eyeCurrH.current, 0.12)
      bone.rotation.x = THREE.MathUtils.lerp(bone.rotation.x, (base?.x ?? 0) + eyeCurrV.current, 0.12)
    }
    applyEye(bones.leftEye); applyEye(bones.rightEye)

    // ── Head ──────────────────────────────────────────────────────────
    if (bones.head) {
      const base = baseRots.get(bones.head)
      // Nod amplitude scales with speech, jaw-dip physically couples head to mouth
      bones.head.rotation.x = (base?.x ?? 0) + Math.sin(t * 0.52) * (0.020 + bEnv * 0.048) + jaw * 0.10 + eyeCurrV.current * 0.30
      bones.head.rotation.y = (base?.y ?? 0) + eyeCurrH.current * 0.42
      bones.head.rotation.z = (base?.z ?? 0) + Math.sin(t * 0.37) * (0.013 + bEnv * 0.022)
    } else if (bones.neck) {
      const base = baseRots.get(bones.neck)
      bones.neck.rotation.x = (base?.x ?? 0) + Math.sin(t * 0.52) * (0.013 + bEnv * 0.032)
      bones.neck.rotation.y = (base?.y ?? 0) + eyeCurrH.current * 0.30
    }

    // ── Spine / chest breathing ───────────────────────────────────────
    const sb2 = bones.chest ?? bones.spine
    if (sb2) {
      const base = baseRots.get(sb2)
      sb2.rotation.x = (base?.x ?? 0) + Math.sin(t * (0.27 + (isSpeaking ? 0.09 : 0))) * (0.005 + bEnv * 0.008)
      sb2.rotation.z = (base?.z ?? 0) + Math.sin(t * 0.28) * (0.003 + bEnv * 0.005)
    }

    // ── Arm gestures ─────────────────────────────────────────────────
    const armActive  = isSpeaking && bEnv > 0.08
    const gestureMag = armActive ? Math.min(0.16, (bEnv - 0.08) * 0.20) : 0

    const applyArm = (bone: THREE.Bone|null, phase: number, zSign: number) => {
      if (!bone) return
      const base = baseRots.get(bone)
      if (armActive) {
        bone.rotation.z = (base?.z ?? 0) + zSign * Math.sin(t * 0.60 + gp + phase) * gestureMag
        bone.rotation.x = (base?.x ?? 0) + Math.sin(t * 0.44 + gp + phase + 1.1) * gestureMag * 0.45
      } else {
        bone.rotation.x = THREE.MathUtils.lerp(bone.rotation.x, base?.x ?? 0, 0.03)
        bone.rotation.z = THREE.MathUtils.lerp(bone.rotation.z, base?.z ?? 0, 0.03)
      }
    }
    applyArm(bones.leftArm,  0,         +1)
    applyArm(bones.rightArm, Math.PI,   -1)
    applyArm(bones.leftFore, 0.5,       +1)
    applyArm(bones.rightFore, Math.PI + 0.5, -1)

    // Fallback scene-root sway when no skeleton found
    if (!bones.head && !bones.neck) {
      scene.rotation.y = Math.sin(t * 0.38) * 0.028 + Math.sin(t * 0.71) * 0.010
    }
  })

  return (
    <>
      <ambientLight intensity={2.85} color={0xf4f6fa} />
      <directionalLight position={[1.2, 2.5, 1.8]} intensity={20} color={0xb8bdd4} />
      <directionalLight position={[-0.8, 1.2, 0.5]} intensity={6} color={0xd0d8f0} />
      <primitive object={scene} />
    </>
  )
}

useGLTF.preload('/mpfb.glb')

// ─── Audio helpers ────────────────────────────────────────────────────────────

async function decodeAudio(ctx: AudioContext, ab: ArrayBuffer): Promise<AudioBuffer> {
  try { return await ctx.decodeAudioData(ab.slice(0)) }
  catch { return await new Promise<AudioBuffer>((res, rej) => ctx.decodeAudioData(ab.slice(0), res, rej)) }
}

const DEFAULT_GLB = '/mpfb.glb'
function resolveGlb() {
  if (typeof process !== 'undefined') {
    const e = process.env.NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB?.trim()
    if (e) return e
  }
  return DEFAULT_GLB
}

// ─── Outer component ──────────────────────────────────────────────────────────

export const SanadiTalkingHead = forwardRef<SanadiTalkingHeadHandle, Props>(
  function SanadiTalkingHead(
    { active, phase, emotion, distressScore: _ds, variant = 'overlay', className, onAssistantAnalyser },
    ref,
  ) {
    const [sceneReady, setSceneReady] = useState(false)
    const [sceneError, setSceneError] = useState<string | null>(null)
    const sceneReadyRef = useRef(false)
    const glbUrl = resolveGlb()

    const audioCtxRef    = useRef<AudioContext | null>(null)
    const analyserRef    = useRef<AnalyserNode | null>(null)
    const sourceRef      = useRef<AudioBufferSourceNode | null>(null)
    const safetyRef      = useRef<number | null>(null)
    const endedRef       = useRef(false)
    const speechIdRef    = useRef(0)

    const onAnalyserRef  = useRef(onAssistantAnalyser)
    useEffect(() => { onAnalyserRef.current = onAssistantAnalyser }, [onAssistantAnalyser])

    const audioBridge = useRef<AudioBridge>({
      analyser: null, isSpeaking: false, audioCtx: null,
      playbackStartCtxTime: 0, visemeSegments: [], speechId: 0,
    })
    const stateBridge = useRef<StateBridge>({ phase: 'idle', emotion: null })

    // Keep state bridge in sync without re-rendering the Canvas
    useEffect(() => { stateBridge.current.phase = phase }, [phase])
    useEffect(() => { stateBridge.current.emotion = emotion ?? null }, [emotion])

    const stopSpeech = useCallback(() => {
      if (safetyRef.current != null) { window.clearTimeout(safetyRef.current); safetyRef.current = null }
      try { sourceRef.current?.stop() } catch { /* ended */ }
      sourceRef.current = null
      audioBridge.current.isSpeaking = false
      audioBridge.current.analyser   = null
      audioBridge.current.audioCtx   = null
      onAnalyserRef.current?.(null)
    }, [])

    const onSceneLoad = useCallback(() => {
      sceneReadyRef.current = true
      setSceneReady(true)
    }, [])

    useImperativeHandle(ref, () => ({
      isAvatarReady: () => sceneReadyRef.current,
      interruptSpeech: stopSpeech,

      speakFromServiceTts: async (speech, replyText, _lang, onEnded) => {
        if (!sceneReadyRef.current) return false
        stopSpeech()
        endedRef.current = false

        if (!audioCtxRef.current || audioCtxRef.current.state === 'closed')
          audioCtxRef.current = new AudioContext()
        const ctx = audioCtxRef.current
        await ctx.resume().catch(() => {})

        let decoded: AudioBuffer
        try { decoded = await decodeAudio(ctx, speech.audioBuf.slice(0)) }
        catch { return false }

        if (!analyserRef.current || analyserRef.current.context !== ctx) {
          const an = ctx.createAnalyser()
          an.fftSize = 512; an.smoothingTimeConstant = 0.25
          an.connect(ctx.destination)
          analyserRef.current = an
        }

        const an     = analyserRef.current
        const source = ctx.createBufferSource()
        source.buffer = decoded
        source.connect(an)
        sourceRef.current = source

        const durMs = decoded.duration * 1000

        // Build viseme timeline — real timestamps preferred, text-estimated fallback
        const segs = speech.words.length > 0
          ? buildSegments(speech.words, speech.wtimes, speech.wdurations)
          : buildSegmentsFromText(replyText, durMs)

        const sid = ++speechIdRef.current

        const finish = () => {
          if (endedRef.current) return
          endedRef.current = true
          stopSpeech()
          onEnded()
        }

        source.onended        = finish
        safetyRef.current     = window.setTimeout(finish, durMs + 900)

        // Arm bridge — useFrame picks up on next animation frame
        audioBridge.current.analyser              = an
        audioBridge.current.isSpeaking            = true
        audioBridge.current.audioCtx              = ctx
        audioBridge.current.visemeSegments        = segs
        audioBridge.current.speechId              = sid
        audioBridge.current.playbackStartCtxTime  = ctx.currentTime   // set just before start
        source.start()
        // Correct start time after actual start (eliminates scheduling latency)
        audioBridge.current.playbackStartCtxTime  = ctx.currentTime

        onAnalyserRef.current?.(an)
        return true
      },
    }), [stopSpeech])

    useEffect(() => {
      if (!active) {
        stopSpeech()
        audioCtxRef.current?.close().catch(() => {})
        audioCtxRef.current = null; analyserRef.current = null
        sceneReadyRef.current = false; setSceneReady(false); setSceneError(null)
      }
      return () => {
        stopSpeech()
        audioCtxRef.current?.close().catch(() => {})
        audioCtxRef.current = null; analyserRef.current = null
      }
    }, [active, stopSpeech])

    if (!active) return null

    const sizeCls =
      variant === 'voiceHero'
        ? 'h-[min(58svh,36rem)] w-[min(92vw,28rem)] max-h-[60vh]'
        : variant === 'overlay'
          ? 'h-[min(28rem,88vw)] w-[min(24rem,92vw)]'
          : 'h-[min(20rem,65vw)] w-[min(18rem,70vw)]'

    const phaseLabel = phase === 'listening' ? 'Sanadi is listening'
      : phase === 'thinking' ? 'Sanadi is thinking'
      : phase === 'speaking' ? 'Sanadi is speaking'
      : 'Sanadi companion'

    return (
      <section
        className={cn('relative flex flex-col items-center outline-none', className)}
        role="application"
        aria-label="3D voice companion avatar"
        aria-labelledby="sanadi-r3f-label"
      >
        <span id="sanadi-r3f-label" className="sr-only">
          {phaseLabel}. Non-photorealistic companion visualization.
        </span>
        <div
          className={cn(
            variant === 'voiceHero'
              ? 'relative overflow-hidden rounded-3xl bg-muted/15'
              : 'relative overflow-hidden rounded-[2rem] bg-gradient-to-b from-card/90 to-muted/50 shadow-[0_26px_56px_-22px_rgb(31_111_120/0.22)] ring-2 ring-primary/25 ring-offset-2 ring-offset-background',
            sizeCls,
          )}
        >
          <AvatarErrorBoundary onError={setSceneError}>
            <Canvas
              className="h-full w-full"
              camera={{ position: [0, 1.5, 0.85], fov: 45 }}
              gl={{ antialias: true, alpha: true }}
              onCreated={({ camera }) => camera.lookAt(0, 1.5, 0)}
            >
              <Suspense fallback={null}>
                <AvatarScene
                  audioRef={audioBridge}
                  stateRef={stateBridge}
                  glbUrl={glbUrl}
                  onLoad={onSceneLoad}
                />
              </Suspense>
            </Canvas>
          </AvatarErrorBoundary>

          {!sceneReady && !sceneError && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/40 px-6 text-center text-xs leading-relaxed text-muted-foreground">
              Preparing calming companion avatar…
            </div>
          )}
          {sceneError && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/40 px-6 text-center text-xs leading-relaxed text-muted-foreground">
              Companion model could not load ({sceneError.slice(0, 140)}). Set
              NEXT_PUBLIC_SANADI_TALKINGHEAD_GLB to a custom HTTPS GLB.
            </div>
          )}
        </div>
      </section>
    )
  },
)
