/** @type {import('next').NextConfig} */
const staticExport = process.env.NEXT_STATIC_EXPORT === '1'

const nextConfig = {
  ...(staticExport ? { output: 'export' } : {}),
  allowedDevOrigins: ['172.19.32.1'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
