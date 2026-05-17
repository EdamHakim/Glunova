'use client'

import { useState } from 'react'
import { useRouter, Link } from '@/i18n/navigation'
import { Mail, Lock, User as UserIcon, Eye, EyeOff, Check, UserPlus, Stethoscope, Heart, Users, ChevronRight, ChevronLeft, Activity, Brain, Shield, Sun, Moon } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { getApiUrls } from '@/lib/auth'
import { useTheme } from '@/app/providers'
import { cn } from '@/lib/utils'
import LanguageSwitcher from '@/components/layout/language-switcher'

type Role = 'patient' | 'doctor' | 'caregiver'

export default function SignupPage() {
  const router = useRouter()
  const t = useTranslations('auth.signup')
  const tc = useTranslations('common')
  const tl = useTranslations('auth.login')
  const [step, setStep] = useState(0)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { isDark, setTheme } = useTheme()

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    role: 'patient' as Role,
    date_of_birth: '',
    gender: '',
    height_cm: '',
    weight_kg: '',
    hypertension: false,
    heart_disease: false,
    smoking_status: '',
    hba1c_level: '',
    blood_glucose_level: '',
    diabetes_type: '',
  })

  function updateField<K extends keyof typeof form>(field: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const isPatient = form.role === 'patient'
  // Step 0: Account info, Step 1: Role & password, Step 2: Health profile (patient only) / Confirm
  const totalSteps = isPatient ? 3 : 2
  const stepLabels = isPatient
    ? [t('stepAccount'), t('stepRole'), t('stepHealth')]
    : [t('stepAccount'), t('stepRole')]

  const canAdvance = () => {
    if (step === 0) return form.first_name && form.last_name && form.username && form.email
    if (step === 1) {
      if (form.password.length < 8) return false
      if (form.password !== form.confirmPassword) return false
      if (!isPatient) return agreedToTerms
      return true
    }
    if (step === 2) return agreedToTerms
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agreedToTerms) return
    if (form.password !== form.confirmPassword) {
      setError(t('passwordsDoNotMatch'))
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const { django } = getApiUrls()
      const submitData = {
        username: form.username,
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        role: form.role,
        ...(isPatient && {
          date_of_birth: form.date_of_birth || null,
          gender: form.gender || null,
          height_cm: form.height_cm ? parseFloat(form.height_cm) : null,
          weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : null,
          hypertension: form.hypertension,
          heart_disease: form.heart_disease,
          smoking_status: form.smoking_status || null,
          hba1c_level: form.hba1c_level ? parseFloat(form.hba1c_level) : null,
          blood_glucose_level: form.blood_glucose_level ? parseInt(form.blood_glucose_level, 10) : null,
          ...(form.diabetes_type ? { diabetes_type: form.diabetes_type } : {}),
        }),
      }
      const response = await fetch(`${django}/api/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submitData),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        const message = typeof data?.detail === 'string' ? data.detail : t('signUpFailed')
        throw new Error(message)
      }
      router.push('/login')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('somethingWentWrong'))
    } finally {
      setIsLoading(false)
    }
  }

  const roleConfig: { role: Role; icon: typeof Stethoscope; desc: string }[] = [
    { role: 'patient', icon: Heart, desc: t('rolePatientDesc') },
    { role: 'doctor', icon: Stethoscope, desc: t('roleDoctorDesc') },
    { role: 'caregiver', icon: Users, desc: t('roleCaregiverDesc') },
  ]

  const roleLabels: Record<Role, string> = {
    patient: t('rolePatient'),
    doctor: t('roleDoctor'),
    caregiver: t('roleCaregiver'),
  }

  const features = [
    { icon: Activity, label: tl('featureMonitoring') },
    { icon: Brain, label: tl('featureAI') },
    { icon: Shield, label: tl('featureSecurity') },
    { icon: Heart, label: tl('featureWellness') },
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
        <div className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-gradient-to-b from-primary/8 via-primary/3 to-transparent lg:hidden" aria-hidden />
        <div className="pointer-events-none absolute bottom-[-12%] left-[-12%] h-[42%] w-[42%] rounded-full bg-health-success/8 blur-[100px]" />

        {/* Top bar */}
        <div className="relative z-20 flex items-center justify-between px-4 pt-4 sm:px-6 sm:pt-6">
          <Link href="/" className="lg:hidden">
            <img
              src={isDark ? '/glunova_dark_logo.png' : '/glunova_logo.png'}
              alt="Glunova"
              className="h-9 w-auto"
            />
          </Link>
          <div className="ms-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <LanguageSwitcher />
          </div>
        </div>

        {/* Form area */}
        <div className="relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-4 py-8 sm:px-8">
          {/* Header */}
          <div className="mb-6 lg:mb-8">
            <h1 className="text-2xl font-bold tracking-tight text-foreground text-center lg:text-start sm:text-3xl">{t('createAccount')}</h1>
            <p className="mt-1 text-sm text-muted-foreground text-center lg:text-start">{t('joinPlatform')}</p>
          </div>

          {/* Step indicator */}
          <div className="mb-6 flex items-center gap-2">
            {stepLabels.map((label, i) => (
              <div key={label} className="flex flex-1 items-center gap-2">
                <button
                  type="button"
                  onClick={() => i < step && setStep(i)}
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all',
                    i < step
                      ? 'bg-primary text-primary-foreground cursor-pointer'
                      : i === step
                        ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                        : 'bg-muted text-muted-foreground',
                  )}
                >
                  {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
                </button>
                <span className={cn('hidden text-xs font-medium sm:block', i === step ? 'text-foreground' : 'text-muted-foreground')}>
                  {label}
                </span>
                {i < totalSteps - 1 && <div className={cn('mx-1 h-px flex-1', i < step ? 'bg-primary' : 'bg-border')} />}
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            <div className={cn('rounded-2xl border border-border/60 bg-card/95 p-5 shadow-xl shadow-black/[0.03] backdrop-blur-sm sm:p-7')}>

              {/* ── Step 0: Account info ─────────────────────────────── */}
              {step === 0 && (
                <div className="space-y-5">
                  <div className="space-y-1">
                    <h2 className="text-base font-semibold">{t('registration')}</h2>
                    <p className="text-sm text-muted-foreground">{t('registrationDesc')}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="first_name" className="text-sm font-medium">{t('firstName')}</Label>
                      <div className="relative group">
                        <UserIcon className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="first_name" type="text" placeholder={t('firstNamePlaceholder')} className="ps-10 h-11 bg-background/60" value={form.first_name} onChange={(e) => updateField('first_name', e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last_name" className="text-sm font-medium">{t('lastName')}</Label>
                      <div className="relative group">
                        <UserIcon className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="last_name" type="text" placeholder={t('lastNamePlaceholder')} className="ps-10 h-11 bg-background/60" value={form.last_name} onChange={(e) => updateField('last_name', e.target.value)} required />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="username" className="text-sm font-medium">{t('username')}</Label>
                      <div className="relative group">
                        <UserIcon className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="username" type="text" placeholder={t('usernamePlaceholder')} className="ps-10 h-11 bg-background/60" value={form.username} onChange={(e) => updateField('username', e.target.value)} required />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email" className="text-sm font-medium">{t('email')}</Label>
                      <div className="relative group">
                        <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="email" type="email" placeholder={t('emailPlaceholder')} className="ps-10 h-11 bg-background/60" value={form.email} onChange={(e) => updateField('email', e.target.value)} required />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Step 1: Role & password ──────────────────────────── */}
              {step === 1 && (
                <div className="space-y-5">
                  <div className="space-y-1">
                    <h2 className="text-base font-semibold">{t('accountType')}</h2>
                    <p className="text-sm text-muted-foreground">{t('chooseRole')}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                    {roleConfig.map(({ role, icon: Icon, desc }) => (
                      <button
                        key={role}
                        type="button"
                        onClick={() => updateField('role', role)}
                        className={cn(
                          'flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-all',
                          form.role === role
                            ? 'border-primary/50 bg-primary/8 text-foreground shadow-sm ring-1 ring-primary/20'
                            : 'border-border/70 bg-background/50 text-muted-foreground hover:border-muted-foreground/30 hover:bg-muted/30',
                        )}
                      >
                        <div className={cn(
                          'flex h-10 w-10 items-center justify-center rounded-full transition-colors',
                          form.role === role ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
                        )}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <span className="text-sm font-semibold">{roleLabels[role]}</span>
                        <span className="text-[11px] leading-snug text-muted-foreground">{desc}</span>
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="password" className="text-sm font-medium">{t('password')}</Label>
                      <div className="relative group">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="password" type={showPassword ? 'text' : 'password'} placeholder={t('passwordPlaceholder')} className="ps-10 pe-10 h-11 bg-background/60" value={form.password} onChange={(e) => updateField('password', e.target.value)} required />
                        <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:text-foreground">
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirmPassword" className="text-sm font-medium">{t('confirmPassword')}</Label>
                      <div className="relative group">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <Input id="confirmPassword" type={showConfirmPassword ? 'text' : 'password'} placeholder={t('passwordPlaceholder')} className="ps-10 pe-10 h-11 bg-background/60" value={form.confirmPassword} onChange={(e) => updateField('confirmPassword', e.target.value)} required />
                        <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)} className="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:text-foreground">
                          {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3 text-[11px] font-medium text-muted-foreground">
                    <span className={cn('flex items-center gap-1', form.password.length >= 8 && 'text-health-success')}><Check className="h-3 w-3" />{t('req8Chars')}</span>
                    <span className={cn('flex items-center gap-1', /[A-Z]/.test(form.password) && 'text-health-success')}><Check className="h-3 w-3" />{t('reqUppercase')}</span>
                    <span className={cn('flex items-center gap-1', /[0-9]/.test(form.password) && 'text-health-success')}><Check className="h-3 w-3" />{t('reqNumber')}</span>
                  </div>

                  {/* Terms (for non-patient, this is the final step) */}
                  {!isPatient && (
                    <div className="flex items-start gap-3 rounded-lg border border-border/60 bg-muted/20 p-3">
                      <Checkbox id="terms" checked={agreedToTerms} onCheckedChange={(checked) => setAgreedToTerms(checked as boolean)} className="mt-0.5" />
                      <label htmlFor="terms" className="text-xs leading-relaxed text-muted-foreground">
                        {t('agreeTerms')}{' '}
                        <Link href="#" className="font-semibold text-primary hover:text-primary/80">{t('termsOfService')}</Link>
                        {' '}{t('and')}{' '}
                        <Link href="#" className="font-semibold text-primary hover:text-primary/80">{tc('privacyPolicy')}</Link>
                      </label>
                    </div>
                  )}
                </div>
              )}

              {/* ── Step 2: Health profile (patient only) ────────────── */}
              {step === 2 && isPatient && (
                <div className="space-y-5">
                  <div className="space-y-1">
                    <h2 className="text-base font-semibold">{t('healthProfile')}</h2>
                    <p className="text-sm text-muted-foreground">{t('healthProfileDesc')}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="dob" className="text-sm font-medium">{t('dateOfBirth')}</Label>
                      <Input id="dob" type="date" className="h-11 bg-background/60" value={form.date_of_birth} onChange={(e) => updateField('date_of_birth', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="gender" className="text-sm font-medium">{t('gender')}</Label>
                      <select id="gender" className="flex h-11 w-full rounded-md border bg-background/60 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={form.gender} onChange={(e) => updateField('gender', e.target.value)}>
                        <option value="">{t('genderSelect')}</option>
                        <option value="Male">{t('genderMale')}</option>
                        <option value="Female">{t('genderFemale')}</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="diabetes_type" className="text-sm font-medium">{t('diabetesType')}</Label>
                    <select id="diabetes_type" className="flex h-11 w-full rounded-md border bg-background/60 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={form.diabetes_type} onChange={(e) => updateField('diabetes_type', e.target.value)}>
                      <option value="">{t('diabetesNotSpecified')}</option>
                      <option value="Type 1">{t('diabetesType1')}</option>
                      <option value="Type 2">{t('diabetesType2')}</option>
                      <option value="Prediabetes">{t('diabetesPrediabetes')}</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="height" className="text-sm font-medium">{t('height')}</Label>
                      <Input id="height" type="number" step="0.1" min="50" max="250" placeholder="170" className="h-11 bg-background/60" value={form.height_cm} onChange={(e) => updateField('height_cm', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="weight" className="text-sm font-medium">{t('weight')}</Label>
                      <Input id="weight" type="number" step="0.1" min="20" max="300" placeholder="70" className="h-11 bg-background/60" value={form.weight_kg} onChange={(e) => updateField('weight_kg', e.target.value)} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="hba1c" className="text-sm font-medium">{t('hba1c')}</Label>
                      <Input id="hba1c" type="number" step="0.1" min="3" max="15" placeholder="5.5" className="h-11 bg-background/60" value={form.hba1c_level} onChange={(e) => updateField('hba1c_level', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="glucose" className="text-sm font-medium">{t('bloodGlucose')}</Label>
                      <Input id="glucose" type="number" min="50" max="500" placeholder="100" className="h-11 bg-background/60" value={form.blood_glucose_level} onChange={(e) => updateField('blood_glucose_level', e.target.value)} />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="smoking" className="text-sm font-medium">{t('smokingStatus')}</Label>
                    <select id="smoking" className="flex h-11 w-full rounded-md border bg-background/60 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={form.smoking_status} onChange={(e) => updateField('smoking_status', e.target.value)}>
                      <option value="">{t('genderSelect')}</option>
                      <option value="never">{t('smokingNever')}</option>
                      <option value="former">{t('smokingFormer')}</option>
                      <option value="current">{t('smokingCurrent')}</option>
                      <option value="ever">{t('smokingEver')}</option>
                      <option value="not current">{t('smokingNotCurrent')}</option>
                      <option value="No Info">{t('smokingNoInfo')}</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="flex items-center gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2.5">
                      <Checkbox id="hypertension" checked={form.hypertension} onCheckedChange={(v) => updateField('hypertension', v as boolean)} />
                      <Label htmlFor="hypertension" className="cursor-pointer text-sm font-medium">{t('hypertension')}</Label>
                    </div>
                    <div className="flex items-center gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2.5">
                      <Checkbox id="heart_disease" checked={form.heart_disease} onCheckedChange={(v) => updateField('heart_disease', v as boolean)} />
                      <Label htmlFor="heart_disease" className="cursor-pointer text-sm font-medium">{t('heartDisease')}</Label>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 rounded-lg border border-border/60 bg-muted/20 p-3">
                    <Checkbox id="terms" checked={agreedToTerms} onCheckedChange={(checked) => setAgreedToTerms(checked as boolean)} className="mt-0.5" />
                    <label htmlFor="terms" className="text-xs leading-relaxed text-muted-foreground">
                      {t('agreeTerms')}{' '}
                      <Link href="#" className="font-semibold text-primary hover:text-primary/80">{t('termsOfService')}</Link>
                      {' '}{t('and')}{' '}
                      <Link href="#" className="font-semibold text-primary hover:text-primary/80">{tc('privacyPolicy')}</Link>
                    </label>
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="mt-4 rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2.5 text-sm font-medium text-destructive">
                  {error}
                </div>
              )}

              {/* Navigation buttons */}
              <div className="mt-6 flex items-center gap-3">
                {step > 0 && (
                  <Button type="button" variant="outline" className="gap-1.5" onClick={() => { setError(null); setStep(step - 1) }}>
                    <ChevronLeft className="h-4 w-4" />
                    {t('back')}
                  </Button>
                )}
                <div className="flex-1" />
                {step < totalSteps - 1 ? (
                  <Button
                    type="button"
                    className="gap-1.5 shadow-md shadow-primary/15"
                    disabled={!canAdvance()}
                    onClick={() => { setError(null); setStep(step + 1) }}
                  >
                    {t('next')}
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    className="gap-2 shadow-md shadow-primary/20"
                    size="lg"
                    disabled={isLoading || !agreedToTerms}
                    onClick={handleSubmit}
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
                        {t('creatingAccount')}
                      </span>
                    ) : (
                      <><UserPlus className="h-4 w-4" />{t('createAccountBtn')}</>
                    )}
                  </Button>
                )}
              </div>
            </div>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              {t('alreadyHaveAccount')}{' '}
              <Link href="/login" className="font-semibold text-primary hover:text-primary/80 transition-colors">{t('signIn')}</Link>
            </p>
          </form>

          <p className="mt-6 flex flex-wrap justify-center gap-x-4 gap-y-1 text-center text-xs text-muted-foreground">
            <Link href="#" className="hover:text-foreground transition-colors">{tc('termsOfService')}</Link>
            <span className="text-border">·</span>
            <Link href="#" className="hover:text-foreground transition-colors">{tc('privacyPolicy')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
