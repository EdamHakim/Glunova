'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useMemo } from 'react'
import {
  LayoutDashboard,
  Stethoscope,
  TrendingUp,
  Apple,
  Brain,
  Users,
  Stethoscope as Clinic,
  Settings,
} from 'lucide-react'
import { useAuth } from '@/components/auth-context'
import type { UserRole } from '@/lib/auth'

type MenuItem = {
  label: string
  href: string
  icon: typeof LayoutDashboard
  allowedRoles?: UserRole[]
}

const menuItems: MenuItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Screening',
    href: '/dashboard/screening',
    icon: Stethoscope,
    allowedRoles: ['patient'],
  },
  {
    label: 'Monitoring',
    href: '/dashboard/monitoring',
    icon: TrendingUp,
  },
  {
    label: 'Nutrition & Activity',
    href: '/dashboard/nutrition',
    icon: Apple,
  },
  {
    label: 'Psychology',
    href: '/dashboard/psychology',
    icon: Brain,
  },
  {
    label: 'Care Circle',
    href: '/dashboard/care-circle',
    icon: Users,
  },
  {
    label: 'Clinical Support',
    href: '/dashboard/clinical',
    icon: Clinic,
    allowedRoles: ['doctor'],
  },
]

export default function Sidebar() {
  const pathname = usePathname()
  const { user } = useAuth()

  const visibleMenuItems = useMemo(() => {
    const role = user?.role
    return menuItems.filter((item) => !item.allowedRoles || (role != null && item.allowedRoles.includes(role)))
  }, [user])

  return (
    <aside className="hidden w-64 border-r border-border bg-sidebar text-sidebar-foreground lg:flex lg:flex-col">
      <div className="flex items-center gap-3 border-b border-sidebar-border px-6 py-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-lg">
          G
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight">Glunova</h1>
          <p className="text-xs text-muted-foreground">AI Healthcare</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-6">
        <ul className="space-y-2">
          {visibleMenuItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-primary'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="border-t border-sidebar-border px-3 py-4">
        <Link
          href="/dashboard/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent/50 transition-colors"
        >
          <Settings className="h-5 w-5" />
          <span>Settings</span>
        </Link>
      </div>
    </aside>
  )
}
