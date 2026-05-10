'use client'

import { useEffect, useState } from 'react'
import { Palette, Type, Globe, Lock, Bell, Eye, Volume2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
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

export default function SettingsPage() {
  const t = useTranslations('settings')
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="text-muted-foreground mt-2">{t('managePreferences')}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            {t('appearance')}
          </CardTitle>
          <CardDescription>{t('appearanceDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {mounted && (
            <div>
              <label className="text-sm font-medium">{t('themeLabel')}</label>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
                <button
                  onClick={() => setTheme('light')}
                  className={`p-4 rounded-lg transition-colors ${
                    theme === 'light'
                      ? 'border-2 border-primary bg-muted'
                      : 'border border-border hover:border-primary'
                  }`}
                >
                  <p className="font-medium text-sm">{t('themeLight')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('lightThemeDesc')}</p>
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  className={`p-4 rounded-lg transition-colors ${
                    theme === 'dark'
                      ? 'border-2 border-primary bg-muted'
                      : 'border border-border hover:border-primary'
                  }`}
                >
                  <p className="font-medium text-sm">{t('themeDark')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('darkThemeDesc')}</p>
                </button>
                <button
                  onClick={() => setTheme('system')}
                  className={`p-4 rounded-lg transition-colors ${
                    theme === 'system'
                      ? 'border-2 border-primary bg-muted'
                      : 'border border-border hover:border-primary'
                  }`}
                >
                  <p className="font-medium text-sm">{t('themeSystem')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('systemThemeDesc')}</p>
                </button>
              </div>
            </div>
          )}

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              <Eye className="h-4 w-4" />
              {t('highContrastMode')}
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">{t('highContrastDesc')}</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 block">{t('colorScheme')}</label>
            <div className="flex flex-wrap gap-3">
              <button className="h-10 w-10 rounded-full bg-health-success hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-health-info hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-health-warning hover:ring-2 ring-offset-2 ring-primary" />
              <button className="h-10 w-10 rounded-full bg-psychology-soft-purple hover:ring-2 ring-offset-2 ring-primary" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Type className="h-5 w-5" />
            {t('typography')}
          </CardTitle>
          <CardDescription>{t('typographyDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <label className="text-sm font-medium">{t('fontSize')}</label>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                { key: 'fontSizeSmall', value: 'Small' },
                { key: 'fontSizeNormal', value: 'Normal' },
                { key: 'fontSizeLarge', value: 'Large' },
                { key: 'fontSizeXLarge', value: 'Extra Large' },
              ].map(({ key, value }) => (
                <button
                  key={value}
                  className={`px-3 py-2 rounded-lg border ${
                    value === 'Normal'
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border hover:border-primary'
                  }`}
                >
                  {t(key as Parameters<typeof t>[0])}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              <Eye className="h-4 w-4" />
              {t('dyslexiaFont')}
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">{t('dyslexiaFontDesc')}</span>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-3 flex items-center gap-2">
              {t('lineHeight')}
            </label>
            <Select defaultValue="normal">
              <SelectTrigger className="w-full sm:w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="compact">{t('lineHeightCompact')}</SelectItem>
                <SelectItem value="normal">{t('lineHeightNormal')}</SelectItem>
                <SelectItem value="relaxed">{t('lineHeightRelaxed')}</SelectItem>
                <SelectItem value="spacious">{t('lineHeightSpacious')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            {t('languageLocalization')}
          </CardTitle>
          <CardDescription>{t('languageLocalizationDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">{t('languageLabel')}</label>
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
              {t('textToSpeech')}
            </label>
            <div className="flex items-start gap-2 sm:items-center">
              <Switch />
              <span className="text-sm text-muted-foreground">{t('textToSpeechDesc')}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            {t('notifications')}
          </CardTitle>
          <CardDescription>{t('notificationsDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">{t('criticalAlerts')}</p>
              <p className="text-xs text-muted-foreground">{t('criticalAlertsDesc')}</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">{t('dailySummary')}</p>
              <p className="text-xs text-muted-foreground">{t('dailySummaryDesc')}</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">{t('appointmentReminders')}</p>
              <p className="text-xs text-muted-foreground">{t('appointmentRemindersDesc')}</p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-start justify-between gap-4 sm:items-center">
            <div>
              <p className="font-medium text-sm">{t('careCircleMessages')}</p>
              <p className="text-xs text-muted-foreground">{t('careCircleMessagesDesc')}</p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            {t('privacySecurity')}
          </CardTitle>
          <CardDescription>{t('privacySecurityDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="outline" className="w-full">{t('changePassword')}</Button>
          <Button variant="outline" className="w-full">{t('twoFactorAuth')}</Button>
          <Button variant="outline" className="w-full">{t('connectedDevices')}</Button>
          <Button variant="outline" className="w-full">{t('dataPrivacy')}</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('systemInfo')}</CardTitle>
          <CardDescription>{t('systemInfoDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">{t('appVersion')}</span>
            <span className="font-medium">1.0.0</span>
          </div>
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">{t('lastUpdated')}</span>
            <span className="font-medium">April 12, 2026</span>
          </div>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">{t('platformLabel')}</span>
            <Badge variant="outline">Glunova AI v3.2</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
