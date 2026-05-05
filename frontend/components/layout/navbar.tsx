'use client'

import Link from 'next/link'
import { Bell, Moon, Search, Settings, Sun, LogOut, User, Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { useAuth } from '@/components/auth-context'
import { useTheme } from '@/app/providers'
import type { UserRole } from '@/lib/auth'

type NavItem = {
  label: string
  href: string
  allowedRoles?: UserRole[]
}

const mobileNavItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', allowedRoles: ['doctor'] },
  { label: 'Screening', href: '/dashboard/screening', allowedRoles: ['patient'] },
  { label: 'Monitoring', href: '/dashboard/monitoring' },
  { label: 'Nutrition', href: '/dashboard/nutrition' },
  { label: 'Sanadi', href: '/dashboard/psychology' },
  { label: 'Care Circle', href: '/dashboard/care-circle', allowedRoles: ['patient', 'caregiver'] },
  { label: 'Clinical', href: '/dashboard/clinical', allowedRoles: ['doctor'] },
  { label: 'Settings', href: '/dashboard/settings' },
]

export default function Navbar() {
  const { user, logout } = useAuth()
  const { isDark, setTheme } = useTheme()

  function toggleAppearance() {
    setTheme(isDark ? 'light' : 'dark')
  }

  async function handleLogout() {
    await logout()
  }

  return (
    <nav className="border-b border-border bg-card px-4 py-3 sm:px-6 sm:py-4">
      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden">
              <Menu className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            {mobileNavItems
              .filter((item) => !item.allowedRoles || (user?.role && item.allowedRoles.includes(user.role)))
              .map((item) => (
                <DropdownMenuItem key={item.href} asChild>
                  <Link href={item.href}>{item.label}</Link>
                </DropdownMenuItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search patients, records..."
            className="pl-10 bg-background border-input"
          />
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="relative text-muted-foreground hover:text-foreground"
          aria-label="Notifications"
          type="button"
        >
          <Bell className="h-5 w-5" aria-hidden />
          <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-health-danger" aria-hidden />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          type="button"
          className="text-muted-foreground hover:text-foreground"
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-pressed={isDark}
          onClick={toggleAppearance}
        >
          {isDark ? <Sun className="h-5 w-5 shrink-0" aria-hidden /> : <Moon className="h-5 w-5 shrink-0" aria-hidden />}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.profile_picture || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username || 'guest'}`} />
                <AvatarFallback>{user?.username?.[0]?.toUpperCase() || 'G'}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium">{user?.username ?? 'Glunova User'}</p>
                <p className="text-xs text-muted-foreground">{user?.role ?? 'guest'}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/profile" className="flex items-center w-full">
                <User className="mr-2 h-4 w-4" />
                <span>Profile</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Settings className="mr-2 h-4 w-4" />
              <span>Settings</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              <span>Logout</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        </div>
      </div>
    </nav>
  )
}
