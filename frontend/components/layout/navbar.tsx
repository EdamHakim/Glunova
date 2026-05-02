'use client'

import Link from 'next/link'
import { Bell, Search, Settings, LogOut, User, Menu } from 'lucide-react'
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
  { label: 'Psychology', href: '/dashboard/psychology' },
  { label: 'Care Circle', href: '/dashboard/care-circle' },
  { label: 'Clinical', href: '/dashboard/clinical', allowedRoles: ['doctor'] },
  { label: 'Settings', href: '/dashboard/settings' },
]

export default function Navbar() {
  const { user, logout } = useAuth()

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
          className="text-muted-foreground hover:text-foreground"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute top-2 right-2 h-2 w-2 bg-health-danger rounded-full" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <Avatar className="h-8 w-8">
                <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=Dr+Smith" />
                <AvatarFallback>DS</AvatarFallback>
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
