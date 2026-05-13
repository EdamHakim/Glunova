import createNextIntlPlugin from 'next-intl/plugin'

const withNextIntl = createNextIntlPlugin('./i18n/request.ts')

// Server-only vars (no NEXT_PUBLIC prefix) — never exposed to the browser
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8001'

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    preloadEntriesOnStart: true,
    optimizePackageImports: ['lucide-react', 'date-fns'],
  },
  allowedDevOrigins: ['172.19.32.1'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      // Django routes
      { source: '/api/:path*',   destination: `${BACKEND_URL}/api/:path*` },
      { source: '/admin/:path*', destination: `${BACKEND_URL}/admin/:path*` },
      { source: '/media/:path*', destination: `${BACKEND_URL}/media/:path*` },
      // FastAPI routes
      { source: '/screening/:path*',  destination: `${FASTAPI_URL}/screening/:path*` },
      { source: '/nutrition/:path*',  destination: `${FASTAPI_URL}/nutrition/:path*` },
      { source: '/psychology/:path*', destination: `${FASTAPI_URL}/psychology/:path*` },
      { source: '/clinic/:path*',     destination: `${FASTAPI_URL}/clinic/:path*` },
      { source: '/monitoring/:path*', destination: `${FASTAPI_URL}/monitoring/:path*` },
      { source: '/extraction/:path*', destination: `${FASTAPI_URL}/extraction/:path*` },
      { source: '/wellness/:path*',   destination: `${FASTAPI_URL}/wellness/:path*` },
      { source: '/kids/:path*',       destination: `${FASTAPI_URL}/kids/:path*` },
      { source: '/agent/:path*',      destination: `${FASTAPI_URL}/agent/:path*` },
      { source: '/health',            destination: `${FASTAPI_URL}/health` },
    ]
  },
}

export default withNextIntl(nextConfig)
