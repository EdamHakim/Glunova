/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    preloadEntriesOnStart: true,
    optimizePackageImports: ['lucide-react', 'date-fns'],
  },
  transpilePackages: ['@met4citizen/talkinghead'],
  allowedDevOrigins: ['172.19.32.1'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
