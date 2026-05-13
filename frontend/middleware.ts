import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { type NextRequest, NextResponse } from 'next/server'

const intlMiddleware = createMiddleware(routing)

// Paths that are proxied to Django/FastAPI via next.config.mjs rewrites.
// The middleware must NOT add a locale prefix to these.
const backendPrefixes = [
  '/api/', '/admin/', '/media/',
  '/screening/', '/nutrition/', '/psychology/', '/clinic/',
  '/monitoring/', '/extraction/', '/wellness/', '/kids/',
  '/agent/', '/health',
]

export default function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl

  // Skip backend-proxied routes and static files
  if (
    pathname.startsWith('/_next/') ||
    pathname.includes('.') ||
    backendPrefixes.some((p) => pathname.startsWith(p) || pathname === p.replace(/\/$/, ''))
  ) {
    return NextResponse.next()
  }

  return intlMiddleware(request) as NextResponse
}

export const config = {
  matcher: [
    '/((?!_next|api|screening|nutrition|psychology|clinic|monitoring|extraction|wellness|kids|agent|health|admin|media|.*\\..*).*)',
  ],
}
