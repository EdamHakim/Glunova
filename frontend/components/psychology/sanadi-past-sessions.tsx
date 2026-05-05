'use client'

import { useEffect, useState } from 'react'
import { Calendar, Loader2, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { getPsychologySessionHistory, type SessionHistoryItem } from '@/lib/psychology-api'
import { cn } from '@/lib/utils'

function humanizeTechnique(s: string) {
  const t = s.replace(/_/g, ' ').trim()
  if (!t) return ''
  return t.charAt(0).toUpperCase() + t.slice(1)
}

function stateBadgeClass(state: string | null) {
  const s = (state || '').toLowerCase()
  if (s.includes('crisis')) return 'border-destructive/40 bg-destructive/10 text-destructive'
  if (s.includes('depressed')) return 'border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300'
  if (s.includes('distressed')) return 'border-amber-500/35 bg-amber-500/10 text-amber-900 dark:text-amber-200'
  if (s.includes('anxious')) return 'border-sky-500/35 bg-sky-500/10 text-sky-900 dark:text-sky-100'
  if (s.includes('neutral')) return 'border-border bg-muted/50 text-muted-foreground'
  return 'border-border bg-muted/40 text-muted-foreground'
}

type Props = {
  patientId: number
  refreshKey?: number
  className?: string
}

export function SanadiPastSessions({ patientId, refreshKey = 0, className }: Props) {
  const [items, setItems] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    async function run() {
      setLoading(true)
      setErr(null)
      try {
        const res = await getPsychologySessionHistory(patientId, 30)
        if (!cancel) setItems(res.items)
      } catch {
        if (!cancel) {
          setErr('Could not load past visits.')
          setItems([])
        }
      } finally {
        if (!cancel) setLoading(false)
      }
    }
    void run()
    return () => {
      cancel = true
    }
  }, [patientId, refreshKey])

  return (
    <Card className={cn('border-border/80 bg-card/80 shadow-md shadow-black/5 backdrop-blur-sm', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/20">
            <Calendar className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <CardTitle className="text-base font-semibold tracking-tight">Past visits</CardTitle>
            <CardDescription className="text-sm leading-relaxed">
              Summaries from sessions you have ended. They help Sanadi stay aligned with your story — stored securely for
              your next visit.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pb-5 pt-0">
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading history…
          </div>
        ) : err ? (
          <p className="py-4 text-sm text-muted-foreground">{err}</p>
        ) : items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-primary/25 bg-primary/4 px-4 py-6 text-sm leading-relaxed text-muted-foreground">
            No completed visits yet. When you end a session, a brief summary appears here for continuity with Sanadi.
          </p>
        ) : (
          <ScrollArea className="h-[min(22rem,50svh)] pr-3">
            <ul className="space-y-3">
              {items.map((it) => (
                <li
                  key={it.session_id}
                  className="rounded-xl border border-border/70 bg-background/70 px-4 py-3 shadow-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <time className="text-xs font-medium text-muted-foreground" dateTime={it.ended_at}>
                      {new Date(it.ended_at).toLocaleString(undefined, {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      })}
                    </time>
                    {it.last_state ? (
                      <Badge variant="outline" className={cn('text-[0.65rem] font-normal', stateBadgeClass(it.last_state))}>
                        {it.last_state}
                      </Badge>
                    ) : null}
                    {it.has_risk_flags ? (
                      <Badge
                        variant="outline"
                        className="border-amber-500/40 bg-amber-500/10 text-[0.65rem] text-amber-900 dark:text-amber-100"
                      >
                        Safety flags logged
                      </Badge>
                    ) : null}
                  </div>
                  {it.excerpt ? (
                    <p className="mt-2 text-sm leading-relaxed text-foreground">{it.excerpt}</p>
                  ) : (
                    <p className="mt-2 text-sm text-muted-foreground">No excerpt captured for this visit.</p>
                  )}
                  {it.techniques.length > 0 ? (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary/70" aria-hidden />
                      {[...new Set(it.techniques)].map((t, i) => (
                        <span
                          key={`${it.session_id}-t-${i}`}
                          className="rounded-full bg-primary/10 px-2 py-0.5 text-[0.65rem] text-primary/95"
                        >
                          {humanizeTechnique(t)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
