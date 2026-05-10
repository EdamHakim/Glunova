'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Link } from '@/i18n/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/components/auth-context'
import type { UserRole } from '@/lib/auth'

type RoleGuardProps = {
  allowedRoles: UserRole[]
  title: string
  description: string
  children: React.ReactNode
}

export default function RoleGuard({
  allowedRoles,
  title,
  description,
  children,
}: RoleGuardProps) {
  const t = useTranslations('roleGuard')
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner />
      </div>
    )
  }

  if (!user || !allowedRoles.includes(user.role)) {
    return (
      <div className="space-y-6 p-4 sm:p-6">
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link href="/dashboard">{t('backToDashboard')}</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
