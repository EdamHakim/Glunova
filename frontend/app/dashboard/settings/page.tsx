'use client'

import { useEffect, useState } from 'react'
import { Palette, Type, Globe, Lock, Bell, Eye, Volume2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTheme } from '@/app/providers'
import { useAuth } from '@/components/auth-context'
import { toast } from 'sonner'

export default function SettingsPage() {
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()
  const { user, refreshUser } = useAuth()
  const [loading, setLoading] = useState(false)


  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h1>
        <p className="text-muted-foreground mt-2">Manage your health profile, accessibility, and account preferences</p>
      </div>



      {/* Appearance Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Appearance
          </CardTitle>
          <CardDescription>Customize how the platform looks</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {mounted && (
            <div>
              <label className="text-sm font-medium">Theme</label>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
              <button
                onClick={() => setTheme('light')}
                className={`p-4 rounded-lg transition-colors ${
                  theme === 'light'
                    ? 'border-2 border-primary bg-muted'
                    : 'border border-border hover:border-primary'
                }`}
              >
                <p className="font-medium text-sm">Light</p>
                <p className="text-xs text-muted-foreground mt-1">Default theme</p>
              </button>
              <button
                onClick={() => setTheme('dark')}
                className={`p-4 rounded-lg transition-colors ${
                  theme === 'dark'
                    ? 'border-2 border-primary bg-muted'
                    : 'border border-border hover:border-primary'
                }`}
              >
                <p className="font-medium text-sm">Dark</p>
                <p className="text-xs text-muted-foreground mt-1">Easier on eyes</p>
              </button>
              <button
                onClick={() => setTheme('system')}
                className={`p-4 rounded-lg transition-colors ${
                  theme === 'system'
                    ? 'border-2 border-primary bg-muted'
                    : 'border border-border hover:border-primary'
                }`}
              >
                <p className="font-medium text-sm">System</p>
                <p className="text-xs text-muted-foreground mt-1">Follow device</p>
              </button>
              </div>
            </div>
          )}

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              <Eye className="h-4 w-4" />
              High Contrast Mode
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">Increased visibility for text and UI elements</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 block">Color Scheme</label>
            <div className="flex flex-wrap gap-3">
              <button className="h-10 w-10 rounded-full bg-health-success hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-health-info hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-health-warning hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-psychology-soft-purple hover:ring-2 ring-offset-2 ring-primary" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Typography Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Type className="h-5 w-5" />
            Typography
          </CardTitle>
          <CardDescription>Adjust text size and readability</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <label className="text-sm font-medium">Font Size</label>
            <div className="mt-3 flex flex-wrap gap-2">
              {['Small', 'Normal', 'Large', 'Extra Large'].map((size) => (
                <button
                  key={size}
                  className={`px-3 py-2 rounded-lg border ${
                    size === 'Normal'
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border hover:border-primary'
                  }`}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              <Eye className="h-4 w-4" />
              Dyslexia-Friendly Font
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">Use OpenDyslexic font for better readability</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              Line Height
            </label>
            <Select defaultValue="normal">
              <SelectTrigger className="w-full sm:w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="compact">Compact (1.4)</SelectItem>
                <SelectItem value="normal">Normal (1.6)</SelectItem>
                <SelectItem value="relaxed">Relaxed (1.8)</SelectItem>
                <SelectItem value="spacious">Spacious (2.0)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Language & Localization */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Language & Localization
          </CardTitle>
          <CardDescription>Select your preferred language</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Language</label>
            <Select defaultValue="en">
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Español</SelectItem>
                <SelectItem value="fr">Français</SelectItem>
                <SelectItem value="de">Deutsch</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
                <SelectItem value="ar">العربية</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              <Volume2 className="h-4 w-4" />
              Text-to-Speech
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">Enable audio narration of text content</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
          </CardTitle>
          <CardDescription>Control how and when you receive alerts</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">Critical Alerts</p>
              <p className="text-xs text-muted-foreground">High-risk patient updates</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">Daily Summary</p>
              <p className="text-xs text-muted-foreground">End-of-day health report</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">Appointment Reminders</p>
              <p className="text-xs text-muted-foreground">Upcoming screening notifications</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">Care Circle Messages</p>
              <p className="text-xs text-muted-foreground">Family & caregiver notifications</p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      {/* Privacy & Security */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Privacy & Security
          </CardTitle>
          <CardDescription>Manage your account security</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="outline" className="w-full">
            Change Password
          </Button>
          <Button variant="outline" className="w-full">
            Two-Factor Authentication
          </Button>
          <Button variant="outline" className="w-full">
            Connected Devices
          </Button>
          <Button variant="outline" className="w-full">
            Data Privacy Settings
          </Button>
        </CardContent>
      </Card>

      {/* System Information */}
      <Card>
        <CardHeader>
          <CardTitle>System Information</CardTitle>
          <CardDescription>Application version and diagnostics</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">Application Version</span>
            <span className="font-medium">1.0.0</span>
          </div>
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">Last Updated</span>
            <span className="font-medium">April 12, 2026</span>
          </div>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">Platform</span>
            <Badge variant="outline">Glunova AI v3.2</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
