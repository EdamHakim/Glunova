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
  Baby,
  Stethoscope as Clinic,
  Settings,
  User,
} from 'lucide-react'
import { useAuth } from '@/components/auth-context'
import { useTheme } from '@/app/providers'
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
    allowedRoles: ['doctor'],
  },
  {
    label: 'Monitoring',
    href: '/dashboard/monitoring',
    icon: TrendingUp,
  },
  {
    label: 'Screening',
    href: '/dashboard/screening',
    icon: Stethoscope,
    allowedRoles: ['patient'],
  },
  {
    label: 'Nutrition & Activity',
    href: '/dashboard/nutrition',
    icon: Apple,
  },
  {
    label: 'Sanadi',
    href: '/dashboard/psychology',
    icon: Brain,
  },
  {
    label: 'Care Circle',
    href: '/dashboard/care-circle',
    icon: Users,
  },
  {
    label: 'Kids',
    href: '/dashboard/kids',
    icon: Baby,
    allowedRoles: ['patient'],
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
  const { isDark } = useTheme()

  const visibleMenuItems = useMemo(() => {
    const role = user?.role
    return menuItems.filter((item) => !item.allowedRoles || (role != null && item.allowedRoles.includes(role)))
  }, [user])

  return (
    <aside className="hidden w-64 border-r border-border bg-sidebar text-sidebar-foreground lg:flex lg:flex-col">
      <Link href="/" className="flex items-center gap-3 border-b border-sidebar-border px-6 py-6 hover:opacity-80 transition-opacity">
        <img 
          src={isDark ? "/glunova_dark_logo.png" : "/glunova_logo.png"} 
          alt="Glunova Logo" 
          className="h-10 w-10 object-contain shrink-0" 
        />
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold tracking-tight truncate">Glunova</h1>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">AI Healthcare</p>
        </div>
      </Link>

      <nav className="flex-1 overflow-y-auto px-3 py-6">
        <ul className="space-y-2">
          {visibleMenuItems.map((item) => {
            const Icon = item.icon
            const isActive = item.href === '/dashboard'
              ? pathname === '/dashboard'
              : pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive
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

      <div className="border-t border-sidebar-border px-3 py-4 space-y-1">
        <Link
          href="/dashboard/profile"
          className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            pathname === '/dashboard/profile'
              ? 'bg-sidebar-accent text-sidebar-primary'
              : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
          }`}
        >
          <User className="h-5 w-5" />
          <span>Profile</span>
        </Link>
        <Link
          href="/dashboard/settings"
          className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            pathname === '/dashboard/settings'
              ? 'bg-sidebar-accent text-sidebar-primary'
              : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
          }`}
        >
          <Settings className="h-5 w-5" />
          <span>Settings</span>
        </Link>
      </div>
    </aside>
  )
}
