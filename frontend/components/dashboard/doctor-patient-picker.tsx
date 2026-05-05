'use client'

import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { getLinkedPatientsForDashboard, type AssignedPatientRow } from '@/lib/dashboard-api'
import { cn } from '@/lib/utils'

export type DoctorPatientPickerProps = {
  id?: string
  value: string
  onChange: (patientId: string) => void
  disabled?: boolean
  className?: string
  label?: string
  description?: string
}

export function DoctorPatientPicker({
  id,
  value,
  onChange,
  disabled,
  className,
  label = 'Patient',
  description,
}: DoctorPatientPickerProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [patients, setPatients] = useState<AssignedPatientRow[]>([])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void getLinkedPatientsForDashboard()
      .then((res) => {
        if (!cancelled) setPatients(res.items)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load patients')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const selected = useMemo(
    () => patients.find((p) => String(p.id) === value),
    [patients, value],
  )

  const singlePatientId = useMemo(
    () => (patients.length === 1 ? patients[0].id : null),
    [patients],
  )

  useEffect(() => {
    if (loading || error || singlePatientId == null || value !== '') return
    onChange(String(singlePatientId))
  }, [loading, error, singlePatientId, value, onChange])

  const triggerDisabled = disabled || loading

  return (
    <div className={cn('space-y-2', className)}>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={triggerDisabled}
            className="w-full justify-between font-normal"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin shrink-0" />
                Loading patients…
              </>
            ) : error ? (
              <span className="text-destructive truncate">Could not load patient list</span>
            ) : selected ? (
              <span className="truncate text-left">{selected.display_name}</span>
            ) : patients.length === 0 ? (
              <span className="text-muted-foreground">No linked patients yet</span>
            ) : (
              <span className="text-muted-foreground">Search by name…</span>
            )}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[min(100vw-2rem,400px)] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search name or username…" />
            <CommandList>
              <CommandEmpty>No patient matches.</CommandEmpty>
              <CommandGroup>
                {patients.map((p) => (
                  <CommandItem
                    key={p.id}
                    value={`${p.display_name} ${p.username} ${p.id}`}
                    onSelect={() => {
                      onChange(String(p.id))
                      setOpen(false)
                    }}
                  >
                    <Check
                      className={cn(
                        'mr-2 h-4 w-4 shrink-0',
                        String(p.id) === value ? 'opacity-100' : 'opacity-0',
                      )}
                    />
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="truncate font-medium">{p.display_name}</span>
                      <span className="truncate text-xs text-muted-foreground">@{p.username}</span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  )
}
