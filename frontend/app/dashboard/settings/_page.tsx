'use client'

import { useEffect, useState } from 'react'
import { Palette, Type, Globe, Check } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { usePathname, useRouter } from '@/i18n/navigation'
import { routing, type Locale } from '@/i18n/routing'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTheme } from '@/app/providers'
import { cn } from '@/lib/utils'

type FontSize = 'small' | 'normal' | 'large' | 'xlarge'
type LineHeight = 'compact' | 'normal' | 'relaxed' | 'spacious'

const FONT_SIZE_MAP: Record<FontSize, string> = {
  small: '14px',
  normal: '16px',
  large: '18px',
  xlarge: '20px',
}

const LINE_HEIGHT_MAP: Record<LineHeight, string> = {
  compact: '1.4',
  normal: '1.6',
  relaxed: '1.8',
  spacious: '2.0',
}

export default function SettingsPage() {
  const t = useTranslations('settings')
  const tl = useTranslations('language')
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()

  const locale = useLocale() as Locale
  const router = useRouter()
  const pathname = usePathname()

  const [fontSize, setFontSizeState] = useState<FontSize>('normal')
  const [lineHeight, setLineHeightState] = useState<LineHeight>('normal')

  useEffect(() => {
    setMounted(true)
    // Load persisted typography settings
    const savedFontSize = localStorage.getItem('glunova-font-size') as FontSize | null
    const savedLineHeight = localStorage.getItem('glunova-line-height') as LineHeight | null
    if (savedFontSize && FONT_SIZE_MAP[savedFontSize]) {
      setFontSizeState(savedFontSize)
      applyFontSize(savedFontSize)
    }
    if (savedLineHeight && LINE_HEIGHT_MAP[savedLineHeight]) {
      setLineHeightState(savedLineHeight)
      applyLineHeight(savedLineHeight)
    }
  }, [])

  function applyFontSize(size: FontSize) {
    document.documentElement.style.fontSize = FONT_SIZE_MAP[size]
  }

  function applyLineHeight(height: LineHeight) {
    document.documentElement.style.lineHeight = LINE_HEIGHT_MAP[height]
  }

  function handleFontSizeChange(size: FontSize) {
    setFontSizeState(size)
    applyFontSize(size)
    localStorage.setItem('glunova-font-size', size)
  }

  function handleLineHeightChange(height: LineHeight) {
    setLineHeightState(height)
    applyLineHeight(height)
    localStorage.setItem('glunova-line-height', height)
  }

  function handleLocaleChange(next: string) {
    router.replace(pathname, { locale: next as Locale })
  }

  const localeLabels: Record<Locale, string> = {
    en: 'English',
    fr: 'Français',
    ar: 'العربية',
  }

  const localeFlags: Record<Locale, string> = {
    en: '🇬🇧',
    fr: '🇫🇷',
    ar: '🇸🇦',
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="text-muted-foreground mt-2">{t('managePreferences')}</p>
      </div>

      {/* ── Appearance ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            {t('appearance')}
          </CardTitle>
          <CardDescription>{t('appearanceDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          {mounted && (
            <div>
              <label className="text-sm font-medium">{t('themeLabel')}</label>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {(['light', 'dark', 'system'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setTheme(mode)}
                    className={cn(
                      'relative rounded-xl border p-4 text-start transition-all',
                      theme === mode
                        ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                        : 'border-border hover:border-muted-foreground/40 hover:bg-muted/30',
                    )}
                  >
                    {theme === mode && (
                      <div className="absolute end-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                        <Check className="h-3 w-3 text-primary-foreground" />
                      </div>
                    )}
                    <p className="text-sm font-semibold">
                      {mode === 'light' ? t('themeLight') : mode === 'dark' ? t('themeDark') : t('themeSystem')}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {mode === 'light' ? t('lightThemeDesc') : mode === 'dark' ? t('darkThemeDesc') : t('systemThemeDesc')}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Typography ─────────────────────────────────────────────── */}
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
              {([
                { key: 'fontSizeSmall', value: 'small' as FontSize },
                { key: 'fontSizeNormal', value: 'normal' as FontSize },
                { key: 'fontSizeLarge', value: 'large' as FontSize },
                { key: 'fontSizeXLarge', value: 'xlarge' as FontSize },
              ]).map(({ key, value }) => (
                <button
                  key={value}
                  onClick={() => handleFontSizeChange(value)}
                  className={cn(
                    'rounded-lg border px-4 py-2.5 text-sm font-medium transition-all',
                    fontSize === value
                      ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                      : 'border-border hover:border-muted-foreground/40 hover:bg-muted/30',
                  )}
                >
                  {t(key as Parameters<typeof t>[0])}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {t('fontSizePreview', { size: FONT_SIZE_MAP[fontSize] })}
            </p>
          </div>

          <div>
            <label className="text-sm font-medium block mb-2">{t('lineHeight')}</label>
            <Select value={lineHeight} onValueChange={(v) => handleLineHeightChange(v as LineHeight)}>
              <SelectTrigger className="w-full sm:w-56">
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

      {/* ── Language ───────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            {t('languageLocalization')}
          </CardTitle>
          <CardDescription>{t('languageLocalizationDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <label className="text-sm font-medium mb-3 block">{t('languageLabel')}</label>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {routing.locales.map((l) => (
              <button
                key={l}
                onClick={() => handleLocaleChange(l)}
                className={cn(
                  'relative flex items-center gap-3 rounded-xl border p-4 transition-all',
                  locale === l
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                    : 'border-border hover:border-muted-foreground/40 hover:bg-muted/30',
                )}
              >
                {locale === l && (
                  <div className="absolute end-3 top-1/2 -translate-y-1/2 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                    <Check className="h-3 w-3 text-primary-foreground" />
                  </div>
                )}
                <span className="text-xl" aria-hidden>{localeFlags[l as Locale]}</span>
                <span className="text-sm font-medium">{localeLabels[l as Locale]}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── System Info ────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>{t('systemInfo')}</CardTitle>
          <CardDescription>{t('systemInfoDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">{t('appVersion')}</span>
            <span className="font-medium">1.0.0</span>
          </div>
          <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
            <span className="text-muted-foreground">{t('lastUpdated')}</span>
            <span className="font-medium">May 17, 2026</span>
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
