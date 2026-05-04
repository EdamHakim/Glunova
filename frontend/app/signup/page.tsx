'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Mail, Lock, User as UserIcon, Eye, EyeOff, Check, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { getApiUrls } from '@/lib/auth'
import { useTheme } from '@/app/providers'
import { cn } from '@/lib/utils'

type Role = 'patient' | 'doctor' | 'caregiver'

export default function SignupPage() {
  const router = useRouter()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { isDark } = useTheme()

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    role: 'patient' as Role,
    // Patient health profile (only sent when role === 'patient').
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agreedToTerms) return
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const { django } = getApiUrls()
      const isPatient = form.role === 'patient'
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
        const message = typeof data?.detail === 'string' ? data.detail : 'Sign up failed.'
        throw new Error(message)
      }

      router.push('/login')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-dvh bg-background">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-linear-to-b from-primary/10 via-primary/4 to-transparent"
        aria-hidden
      />
      <div className="pointer-events-none absolute bottom-[-12%] left-[-12%] h-[42%] w-[42%] rounded-full bg-health-success/10 blur-[100px]" />
      <div className="pointer-events-none absolute top-[15%] right-[-18%] h-[38%] w-[38%] rounded-full bg-primary/8 blur-[95px]" />

      <div className="relative z-10 mx-auto w-full max-w-lg px-4 py-10 sm:px-6 sm:py-14">
        <Link href="/" className="mb-8 block text-center transition-opacity hover:opacity-90">
          <img
            src={isDark ? '/glunova_dark_logo.png' : '/glunova_logo.png'}
            alt="Glunova"
            className="mx-auto mb-4 h-20 w-auto object-contain"
          />
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Glunova</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Create your account</h1>
          <p className="mt-2 text-sm font-medium text-muted-foreground">Join the platform for AI-assisted diabetes care</p>
        </Link>

        <div
          className={cn(
            'rounded-2xl border border-border/70 bg-card/95 p-6 shadow-xl shadow-black/5',
            'backdrop-blur-sm sm:p-8',
          )}
        >
          <div className="mb-6 space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Registration</h2>
            <p className="text-sm text-muted-foreground">Fill in your details. Patient accounts can add an optional health profile.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* First Name */}
              <div className="space-y-2">
                <Label htmlFor="first_name" className="text-sm font-semibold ml-1 text-foreground">
                  First Name
                </Label>
                <div className="relative group">
                  <UserIcon className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="first_name"
                    type="text"
                    placeholder="John"
                    className="pl-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.first_name}
                    onChange={(e) => updateField('first_name', e.target.value)}
                    required
                  />
                </div>
              </div>
              {/* Last Name */}
              <div className="space-y-2">
                <Label htmlFor="last_name" className="text-sm font-semibold ml-1 text-foreground">
                  Last Name
                </Label>
                <div className="relative group">
                  <UserIcon className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="last_name"
                    type="text"
                    placeholder="Doe"
                    className="pl-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.last_name}
                    onChange={(e) => updateField('last_name', e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Username Input */}
              <div className="space-y-2">
                <Label htmlFor="username" className="text-sm font-semibold ml-1 text-foreground">
                  Username
                </Label>
                <div className="relative group">
                  <UserIcon className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="username"
                    type="text"
                    placeholder="johndoe123"
                    className="pl-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.username}
                    onChange={(e) => updateField('username', e.target.value)}
                    required
                  />
                </div>
              </div>
              {/* Email Input */}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-semibold ml-1 text-foreground">
                  Email
                </Label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="john@example.com"
                    className="pl-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.email}
                    onChange={(e) => updateField('email', e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            {/* Role Selection */}
            <div className="space-y-2">
              <Label className="text-sm font-medium text-foreground">Account type</Label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {(['patient', 'doctor', 'caregiver'] as Role[]).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => updateField('role', r)}
                    className={cn(
                      'rounded-xl border px-3 py-2.5 text-center text-xs font-semibold transition-all',
                      form.role === r
                        ? 'border-primary/50 bg-primary/10 text-primary shadow-sm ring-1 ring-primary/15'
                        : 'border-border/80 bg-background/60 text-muted-foreground hover:border-muted-foreground/30 hover:bg-muted/40',
                    )}
                  >
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Password Input */}
              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-semibold ml-1 text-foreground">
                  Password
                </Label>
                <div className="relative group">
                  <Lock className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    className="pl-10 pr-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.password}
                    onChange={(e) => updateField('password', e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded-md hover:bg-muted"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              {/* Confirm Password Input */}
              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-sm font-semibold ml-1 text-foreground">
                  Confirm
                </Label>
                <div className="relative group">
                  <Lock className="absolute left-3 top-3 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    className="pl-10 pr-10 h-11 bg-background/50 border-muted focus-visible:ring-primary/20 transition-all"
                    value={form.confirmPassword}
                    onChange={(e) => updateField('confirmPassword', e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-3 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded-md hover:bg-muted"
                  >
                    {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Password Requirements */}
            <div className="space-y-2 rounded-xl border border-border/60 bg-muted/25 p-4">
              <p className="text-xs font-semibold text-foreground">Password requirements</p>
              <ul className="space-y-1.5 text-[11px] font-medium text-muted-foreground">
                <li className="flex items-center gap-2">
                  <Check className={`h-3 w-3 ${form.password.length >= 8 ? 'text-health-success' : 'text-muted'}`} />
                  At least 8 characters
                </li>
                <li className="flex items-center gap-2">
                  <Check className={`h-3 w-3 ${/[A-Z]/.test(form.password) ? 'text-health-success' : 'text-muted'}`} />
                  One uppercase letter
                </li>
                <li className="flex items-center gap-2">
                  <Check className={`h-3 w-3 ${/[0-9]/.test(form.password) ? 'text-health-success' : 'text-muted'}`} />
                  One number
                </li>
              </ul>
            </div>

            {/* Health profile — patient only */}
            {form.role === 'patient' && (
              <div className="space-y-4 rounded-xl border border-primary/20 bg-primary/4 p-4 sm:p-5 dark:bg-primary/8">
                <div className="flex flex-col gap-1 border-b border-border/50 pb-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Health profile</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Optional — improves AI risk assessment and wellness planning.
                    </p>
                  </div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-primary">Patient only</span>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="dob" className="text-sm font-semibold ml-1 text-foreground">Date of birth</Label>
                    <Input
                      id="dob"
                      type="date"
                      className="h-11 bg-background/50 border-muted focus-visible:ring-primary/20"
                      value={form.date_of_birth}
                      onChange={(e) => updateField('date_of_birth', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="gender" className="text-sm font-semibold ml-1 text-foreground">Gender</Label>
                    <select
                      id="gender"
                      className="flex h-11 w-full rounded-md border border-muted bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                      value={form.gender}
                      onChange={(e) => updateField('gender', e.target.value)}
                    >
                      <option value="">Select...</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="diabetes_type" className="text-sm font-semibold ml-1 text-foreground">
                    Diabetes type{' '}
                    <span className="font-normal text-muted-foreground">(optional)</span>
                  </Label>
                  <select
                    id="diabetes_type"
                    className="flex h-11 w-full rounded-md border border-muted bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                    value={form.diabetes_type}
                    onChange={(e) => updateField('diabetes_type', e.target.value)}
                  >
                    <option value="">Not specified</option>
                    <option value="Type 1">Type 1</option>
                    <option value="Type 2">Type 2</option>
                    <option value="Prediabetes">Prediabetes</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="height" className="text-sm font-semibold ml-1 text-foreground">Height (cm)</Label>
                    <Input
                      id="height"
                      type="number"
                      step="0.1"
                      min="50"
                      max="250"
                      placeholder="170"
                      className="h-11 bg-background/50 border-muted focus-visible:ring-primary/20"
                      value={form.height_cm}
                      onChange={(e) => updateField('height_cm', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="weight" className="text-sm font-semibold ml-1 text-foreground">Weight (kg)</Label>
                    <Input
                      id="weight"
                      type="number"
                      step="0.1"
                      min="20"
                      max="300"
                      placeholder="70"
                      className="h-11 bg-background/50 border-muted focus-visible:ring-primary/20"
                      value={form.weight_kg}
                      onChange={(e) => updateField('weight_kg', e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="hba1c" className="text-sm font-semibold ml-1 text-foreground">HbA1c (%)</Label>
                    <Input
                      id="hba1c"
                      type="number"
                      step="0.1"
                      min="3"
                      max="15"
                      placeholder="5.5"
                      className="h-11 bg-background/50 border-muted focus-visible:ring-primary/20"
                      value={form.hba1c_level}
                      onChange={(e) => updateField('hba1c_level', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="glucose" className="text-sm font-semibold ml-1 text-foreground">Blood glucose (mg/dL)</Label>
                    <Input
                      id="glucose"
                      type="number"
                      min="50"
                      max="500"
                      placeholder="100"
                      className="h-11 bg-background/50 border-muted focus-visible:ring-primary/20"
                      value={form.blood_glucose_level}
                      onChange={(e) => updateField('blood_glucose_level', e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="smoking" className="text-sm font-semibold ml-1 text-foreground">Smoking status</Label>
                  <select
                    id="smoking"
                    className="flex h-11 w-full rounded-md border border-muted bg-background/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                    value={form.smoking_status}
                    onChange={(e) => updateField('smoking_status', e.target.value)}
                  >
                    <option value="">Select...</option>
                    <option value="never">Never smoked</option>
                    <option value="former">Former smoker</option>
                    <option value="current">Current smoker</option>
                    <option value="ever">Ever smoked</option>
                    <option value="not current">Not current</option>
                    <option value="No Info">Prefer not to say</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="hypertension"
                      checked={form.hypertension}
                      onCheckedChange={(v) => updateField('hypertension', v as boolean)}
                    />
                    <Label htmlFor="hypertension" className="cursor-pointer text-sm font-medium">
                      Hypertension
                    </Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="heart_disease"
                      checked={form.heart_disease}
                      onCheckedChange={(v) => updateField('heart_disease', v as boolean)}
                    />
                    <Label htmlFor="heart_disease" className="cursor-pointer text-sm font-medium">
                      Heart disease
                    </Label>
                  </div>
                </div>
              </div>
            )}

            {/* Terms Agreement */}
            <div className="flex items-start gap-3 pt-2">
              <Checkbox
                id="terms"
                checked={agreedToTerms}
                onCheckedChange={(checked) => setAgreedToTerms(checked as boolean)}
                className="mt-1 translate-y-0.5"
              />
              <label htmlFor="terms" className="text-[13px] text-muted-foreground leading-relaxed font-medium">
                I agree to the{' '}
                <Link href="#" className="font-bold text-primary hover:text-primary/80 transition-colors">
                  Terms of Service
                </Link>
                {' '}and{' '}
                <Link href="#" className="font-bold text-primary hover:text-primary/80 transition-colors">
                  Privacy Policy
                </Link>
              </label>
            </div>

            {error && (
              <div className="rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2.5 text-sm font-medium text-destructive">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="mt-2 h-12 w-full gap-2 text-base font-semibold shadow-md shadow-primary/20"
              size="lg"
              disabled={isLoading || !agreedToTerms}
            >
              {isLoading ? (
                'Creating account…'
              ) : (
                <>
                  <UserPlus className="h-4 w-4" />
                  Create account
                </>
              )}
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link href="/login" className="font-semibold text-primary hover:text-primary/80">
              Sign in
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
