'use client'

import { useEffect, useRef } from 'react'

export type WaveformSpeaker = 'patient' | 'assistant' | 'idle'

type Props = {
  analyserRef: React.MutableRefObject<AnalyserNode | null>
  speaker: WaveformSpeaker
  barCount?: number
  height?: number
  className?: string
}

function readCssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return raw || fallback
}

/**
 * RMS-driven bars when `analyserRef` holds a live node; gentle idle ripple otherwise.
 */
export function SanadiVoiceWaveform({ analyserRef, speaker, barCount = 48, height = 56, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const tRef = useRef(0)

  useEffect(() => {
    let raf = 0

    const draw = () => {
      const canvas = canvasRef.current
      const patientColor = readCssVar('--sanadi-wave-patient', '#d4a373')
      const assistantColor = readCssVar('--sanadi-wave-assistant', '#6fafb7')

      if (!canvas) {
        raf = requestAnimationFrame(draw)
        return
      }
      const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
      const w = canvas.clientWidth
      const drawH = height
      if (w <= 0) {
        raf = requestAnimationFrame(draw)
        return
      }

      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(drawH * dpr)
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        raf = requestAnimationFrame(draw)
        return
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, drawH)

      let accent = speaker === 'assistant' ? assistantColor : patientColor
      let secondary = speaker === 'assistant' ? patientColor : assistantColor
      if (speaker === 'idle') {
        accent = `${patientColor}b3`
        secondary = `${assistantColor}91`
      }

      const analyser = analyserRef.current
      const binCount = analyser?.frequencyBinCount ?? 0
      const freq = binCount ? new Uint8Array(binCount) : null
      if (analyser && freq) {
        analyser.getByteFrequencyData(freq)
      }

      tRef.current += 0.045

      let sumBins = 0
      if (freq) {
        for (let b = 0; b < freq.length; b++) sumBins += freq[b]
      }
      const hasAnalyserEnergy = !!(freq && sumBins > 40)

      const gap = Math.max(1, Math.round(w / barCount / 22))
      const innerW = w - gap
      const barW = innerW / barCount - gap

      const bars: number[] = []
      for (let i = 0; i < barCount; i++) {
        let level = 0
        if (freq && freq.length && hasAnalyserEnergy) {
          const start = Math.floor((i / barCount) * freq.length)
          const slice = Math.max(2, Math.floor(freq.length / barCount))
          let acc = 0
          let n = 0
          for (let j = 0; j < slice && start + j < freq.length; j++) {
            acc += freq[start + j]
            n++
          }
          level = n ? ((acc / n) / 255) * (drawH - 10) + 6 : 0
        }

        let hBar = Math.max(level, 0)

        const idleRipple = !hasAnalyserEnergy || speaker === 'idle'
        if (idleRipple) {
          const tip = speaker === 'assistant' ? 0.12 : 0.08
          hBar = Math.max(
            hBar,
            drawH *
              ((speaker === 'idle' ? 0.42 : 0.36) + Math.sin(tRef.current + i * 0.2) * (speaker === 'idle' ? tip : tip + 0.06)),
          )
        }

        hBar = Math.min(drawH - 8, Math.max(hBar, 6))
        bars.push(hBar)
      }

      const gapAdjust = speaker === 'patient' ? 2 : speaker === 'assistant' ? -1 : 0

      for (let i = 0; i < barCount; i++) {
        const bx = gap + i * (barW + gap) + gapAdjust * 0.5
        const hBar = bars[i] ?? 6
        const y = drawH - hBar
        const radius = Math.min(barW / 2, 5)
        const grad = ctx.createLinearGradient(0, y, 0, drawH)
        grad.addColorStop(0, accent)
        grad.addColorStop(1, secondary)
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.roundRect(bx, y, barW, hBar, radius)
        ctx.fill()
      }

      raf = requestAnimationFrame(draw)
    }

    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [analyserRef, speaker, barCount, height])

  return <canvas ref={canvasRef} className={className} style={{ height, width: '100%' }} />
}
