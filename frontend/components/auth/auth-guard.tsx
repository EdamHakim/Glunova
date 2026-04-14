'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Spinner } from '@/components/ui/spinner'
import { getAccessToken } from '@/lib/auth'

type AuthGuardProps = {
  children: React.ReactNode
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter()
  const pathname = usePathname()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    const token = getAccessToken()
    if (!token) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
      return
    }
    setChecked(true)
  }, [pathname, router])

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner />
      </div>
    )
  }

  return <>{children}</>
}
