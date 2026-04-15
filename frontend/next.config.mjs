/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ['172.19.32.1'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
