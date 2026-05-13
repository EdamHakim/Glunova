import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { type NextRequest, NextResponse } from 'next/server'

const intlMiddleware = createMiddleware(routing)

export default function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl

  // Skip API routes and static files
  if (
    pathname.startsWith('/api/') ||
    pathname.startsWith('/_next/') ||
    pathname.includes('.')
  ) {
    return NextResponse.next()
  }

  return intlMiddleware(request) as NextResponse
}

export const config = {
  matcher: [
    '/((?!_next|api|.*\\..*).*)',
  ],
}
