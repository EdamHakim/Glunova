'use client'

import { useState, Suspense } from 'react'
import { useRouter, Link } from '@/i18n/navigation'
import { useSearchParams } from 'next/navigation'
import { Lock, Eye, EyeOff, User as UserIcon, LogIn, Activity, Shield, Brain, Heart } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/components/auth-context'
import { useTheme } from '@/app/providers'
import { cn } from '@/lib/utils'
import LanguageSwitcher from '@/components/layout/language-switcher'

function LoginForm() {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [localLoading, setLocalLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const t = useTranslations('auth.login')
  const tc = useTranslations('common')
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
        router.push(user?.role === 'doctor' ? '/dashboard' : '/dashboard/monitoring')
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : t('invalidCredentials'))
    } finally {
      setLocalLoading(false)
    }
  }

  const features = [
    { icon: Activity, label: t('featureMonitoring') },
    { icon: Brain, label: t('featureAI') },
    { icon: Shield, label: t('featureSecurity') },
    { icon: Heart, label: t('featureWellness') },
  ]

  return (
    <div className="relative flex h-dvh overflow-hidden bg-background">
      {/* ── Left branding panel (desktop only) ────────────────────── */}
      <div className="hidden w-[45%] flex-col justify-between overflow-hidden bg-gradient-to-br from-[#0a2528] via-[#0f3035] to-[#143a40] p-10 text-white lg:flex xl:w-[42%]">
        <div>
          <Link href="/" className="inline-flex items-center gap-3 transition-opacity hover:opacity-90">
            <img src="/glunova_dark_logo.png" alt="Glunova" className="h-10 w-auto" />
            <span className="text-lg font-bold tracking-tight">Glunova</span>
          </Link>
        </div>

        <div className="space-y-8">
          <div className="max-w-sm space-y-3">
            <h2 className="text-3xl font-bold leading-tight xl:text-4xl">{t('brandHeadline')}</h2>
            <p className="text-sm leading-relaxed text-white/70 xl:text-base">{t('brandSubtext')}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {features.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-3 rounded-xl bg-white/10 px-4 py-3 backdrop-blur-sm">
                <Icon className="h-5 w-5 shrink-0 text-white/80" />
                <span className="text-xs font-medium text-white/90 xl:text-sm">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-white/50">
          &copy; {new Date().getFullYear()} Glunova &mdash; AI-Powered Diabetes Care
        </p>
      </div>

      {/* ── Right form panel ──────────────────────────────────────── */}
      <div className="relative flex flex-1 flex-col overflow-y-auto">
        {/* Background decoration */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-gradient-to-b from-primary/8 via-primary/3 to-transparent lg:hidden" aria-hidden />
        <div className="pointer-events-none absolute bottom-[-15%] right-[-15%] h-[45%] w-[45%] rounded-full bg-health-info/8 blur-[100px]" />

        {/* Top bar with language switcher */}
        <div className="relative z-20 flex items-center justify-between px-4 pt-4 sm:px-6 sm:pt-6">
          <Link href="/" className="lg:hidden">
            <img
              src={isDark ? '/glunova_dark_logo.png' : '/glunova_logo.png'}
              alt="Glunova"
              className="h-9 w-auto"
            />
          </Link>
          <div className="ms-auto">
            <LanguageSwitcher />
          </div>
        </div>

        {/* Centered form */}
        <div className="relative z-10 mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-8 sm:px-8">
          {/* Mobile-only header */}
          <div className="mb-8 text-center lg:hidden">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">{t('welcomeBack')}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{t('signInToDashboard')}</p>
          </div>

          {/* Desktop header */}
          <div className="mb-8 hidden lg:block">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">{t('welcomeBack')}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{t('signInToDashboard')}</p>
          </div>

          <div className={cn('rounded-2xl border border-border/60 bg-card/95 p-6 shadow-xl shadow-black/[0.03] backdrop-blur-sm sm:p-8')}>
            <div className="mb-6 space-y-1">
              <h2 className="text-lg font-semibold text-foreground">{t('accountAccess')}</h2>
              <p className="text-sm text-muted-foreground">{t('accountAccessDesc')}</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-sm font-medium">{t('username')}</Label>
                <div className="relative group">
                  <UserIcon className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                  <Input
                    id="username"
                    type="text"
                    placeholder={t('usernamePlaceholder')}
                    autoComplete="username"
                    className="h-11 bg-background/80 ps-10"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium">{t('password')}</Label>
                <div className="relative group">
                  <Lock className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder={t('passwordPlaceholder')}
                    autoComplete="current-password"
                    className="h-11 bg-background/80 ps-10 pe-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    aria-label={showPassword ? t('hidePassword') : t('showPassword')}
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
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
                    {t('signingIn')}
                  </span>
                ) : (
                  <><LogIn className="h-4 w-4" />{t('signIn')}</>
                )}
              </Button>
            </form>

            <p className="mt-8 text-center text-sm text-muted-foreground">
              {t('noAccount')}{' '}
              <Link href="/signup" className="font-semibold text-primary hover:text-primary/80 transition-colors">
                {t('createOne')}
              </Link>
            </p>
          </div>

          <p className="mt-8 flex flex-wrap justify-center gap-x-4 gap-y-1 text-center text-xs text-muted-foreground">
            <Link href="#" className="hover:text-foreground transition-colors">{tc('termsOfService')}</Link>
            <span className="text-border">·</span>
            <Link href="#" className="hover:text-foreground transition-colors">{tc('privacyPolicy')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

function LoginPageInner() {
  const t = useTranslations('auth.login')
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center bg-background p-6 text-muted-foreground">
          {t('pageLoading')}
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}

export default function LoginPage() {
  return <LoginPageInner />
}
