'use client'

import { useState, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Lock, Eye, EyeOff, User as UserIcon, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/components/auth-context'
import { useTheme } from '@/app/providers'
import { cn } from '@/lib/utils'

function LoginForm() {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [localLoading, setLocalLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const { login } = useAuth()
  const { isDark } = useTheme()
  const router = useRouter()
  const searchParams = useSearchParams()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalLoading(true)
    setLocalError(null)

    try {
      const user = await login(username, password)
      const next = searchParams.get('next')
      if (next) {
        router.push(next)
      } else {
        const landingPage = user?.role === 'doctor' ? '/dashboard' : '/dashboard/monitoring'
        router.push(landingPage)
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Invalid credentials. Please try again.')
    } finally {
      setLocalLoading(false)
    }
  }

  return (
    <div className="relative min-h-dvh bg-background">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-linear-to-b from-primary/10 via-primary/4 to-transparent"
        aria-hidden
      />
      <div className="absolute bottom-[-15%] right-[-15%] h-[45%] w-[45%] rounded-full bg-health-info/10 blur-[100px] pointer-events-none" />
      <div className="absolute top-[20%] left-[-20%] h-[35%] w-[35%] rounded-full bg-primary/8 blur-[90px] pointer-events-none" />

      <div className="relative z-10 mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4 py-10 sm:px-6 sm:py-14">
        <Link
          href="/"
          className="mb-8 block text-center transition-opacity hover:opacity-90"
        >
          <img
            src={isDark ? '/glunova_dark_logo.png' : '/glunova_logo.png'}
            alt="Glunova"
            className="mx-auto mb-4 h-20 w-auto object-contain"
          />
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Glunova</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Welcome back</h1>
          <p className="mt-2 text-sm font-medium text-muted-foreground">Sign in to your health dashboard</p>
        </Link>

        <div
          className={cn(
            'rounded-2xl border border-border/70 bg-card/95 p-6 shadow-xl shadow-black/5',
            'backdrop-blur-sm sm:p-8',
          )}
        >
          <div className="mb-6 space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Account access</h2>
            <p className="text-sm text-muted-foreground">Use the username and password you registered with.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">
                Username
              </Label>
              <div className="relative group">
                <UserIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                <Input
                  id="username"
                  type="text"
                  placeholder="Your username"
                  autoComplete="username"
                  className="h-11 bg-background/80 pl-10"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="password" className="text-sm font-medium">
                  Password
                </Label>
                <Link
                  href="/auth/forgot-password"
                  className="text-xs font-semibold text-primary hover:text-primary/80"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative group">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="h-11 bg-background/80 pl-10 pr-10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {localError && (
              <div className="rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2.5 text-sm font-medium text-destructive">
                {localError}
              </div>
            )}

            <Button
              type="submit"
              className="mt-2 h-12 w-full gap-2 text-base font-semibold shadow-md shadow-primary/20"
              size="lg"
              disabled={localLoading}
            >
              {localLoading ? (
                'Signing in…'
              ) : (
                <>
                  <LogIn className="h-4 w-4" />
                  Sign in
                </>
              )}
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="font-semibold text-primary hover:text-primary/80">
              Create one
            </Link>
          </p>
        </div>

        <p className="mt-8 flex flex-wrap justify-center gap-x-4 gap-y-1 text-center text-xs text-muted-foreground">
          <Link href="#" className="hover:text-foreground">
            Terms of Service
          </Link>
          <span className="text-border">·</span>
          <Link href="#" className="hover:text-foreground">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center bg-background p-6 text-muted-foreground">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
