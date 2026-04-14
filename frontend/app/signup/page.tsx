'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiUrls } from '@/lib/auth'

type Role = 'patient' | 'doctor' | 'caregiver'

export default function SignupPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'patient' as Role,
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function updateField<K extends keyof typeof form>(field: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const { django } = getApiUrls()
      const response = await fetch(`${django}/api/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        const message = typeof data?.detail === 'string' ? data.detail : 'Sign up failed.'
        throw new Error(message)
      }

      router.push('/login')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Sign up failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Create your Glunova account</CardTitle>
          <CardDescription>Register as patient, doctor, or caregiver.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              placeholder="First name"
              value={form.first_name}
              onChange={(event) => updateField('first_name', event.target.value)}
              required
            />
            <Input
              placeholder="Last name"
              value={form.last_name}
              onChange={(event) => updateField('last_name', event.target.value)}
              required
            />
            <Input
              placeholder="Username"
              value={form.username}
              onChange={(event) => updateField('username', event.target.value)}
              required
            />
            <Input
              placeholder="Email"
              type="email"
              value={form.email}
              onChange={(event) => updateField('email', event.target.value)}
              required
            />
            <Input
              className="md:col-span-2"
              placeholder="Password"
              type="password"
              value={form.password}
              onChange={(event) => updateField('password', event.target.value)}
              required
              minLength={8}
            />
            <select
              className="md:col-span-2 h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={form.role}
              onChange={(event) => updateField('role', event.target.value as Role)}
            >
              <option value="patient">Patient</option>
              <option value="doctor">Doctor</option>
              <option value="caregiver">Caregiver</option>
            </select>

            {error ? <p className="md:col-span-2 text-sm text-destructive">{error}</p> : null}

            <Button className="md:col-span-2" type="submit" disabled={loading}>
              {loading ? 'Creating account...' : 'Create account'}
            </Button>
          </form>

          <p className="text-sm text-muted-foreground mt-4">
            Already have an account?{' '}
            <Link href="/login" className="text-primary hover:underline">
              Login
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
