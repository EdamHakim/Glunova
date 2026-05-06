'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Moon,
  Settings,
  Sun,
  LogOut,
  User,
  Menu,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { cn } from '@/lib/utils'

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
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const { isDark, setTheme } = useTheme()

  function toggleAppearance() {
    setTheme(isDark ? 'light' : 'dark')
  }

  async function handleLogout() {
    await logout()
  }

  const mobileLinks = mobileNavItems.filter(
    (item) => !item.allowedRoles || (user?.role && item.allowedRoles.includes(user.role)),
  )

  return (
    <nav
      className={cn(
        'sticky top-0 z-40 shrink-0 border-b border-border/80',
        'bg-background/85 backdrop-blur-md supports-[backdrop-filter]:bg-background/70',
      )}
    >
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:h-[3.75rem] sm:px-6">
        {/* Brand + mobile nav */}
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 lg:hidden"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56" sideOffset={6}>
              {mobileLinks.map((item) => (
                <DropdownMenuItem key={item.href} asChild className={cn(pathname === item.href && 'bg-accent')}>
                  <Link href={item.href}>{item.label}</Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <Link
            href="/dashboard"
            className="rounded-md px-2 py-1.5 text-sm font-semibold tracking-tight text-foreground outline-none ring-offset-background transition-colors hover:bg-muted/80 focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          >
            Dashboard
          </Link>

          {/* Context (logo lives in sidebar on lg+) */}
          <div className="ml-2 hidden min-w-0 flex-1 md:block lg:ml-0">
            {pathname.startsWith('/dashboard') && pathname !== '/dashboard' && (
              <p className="truncate border-l border-border pl-4 text-sm text-muted-foreground">
                {pathname
                  .split('/')
                  .filter(Boolean)
                  .slice(1)
                  .map((segment) =>
                    segment
                      .replace(/-/g, ' ')
                      .replace(/\b\w/g, (c) => c.toUpperCase()),
                  )
                  .join(' · ')}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-0.5 sm:gap-1">
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
              <Button variant="ghost" size="icon" className="rounded-full" aria-label="Account menu">
                <Avatar className="h-8 w-8 border border-border/60 shadow-sm">
                  <AvatarImage
                    src={
                      user?.profile_picture ||
                      `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username || 'guest'}`
                    }
                  />
                  <AvatarFallback className="text-xs font-semibold">{user?.username?.[0]?.toUpperCase() || 'G'}</AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56" sideOffset={8}>
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium">{user?.username ?? 'Glunova User'}</p>
                  <p className="text-xs capitalize text-muted-foreground">{user?.role ?? 'guest'}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/dashboard/profile" className="flex w-full items-center cursor-pointer">
                  <User className="mr-2 h-4 w-4" />
                  <span>Profile</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/dashboard/settings" className="flex w-full items-center cursor-pointer">
                  <Settings className="mr-2 h-4 w-4" />
                  <span>Settings</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer text-destructive focus:text-destructive" onClick={handleLogout}>
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
