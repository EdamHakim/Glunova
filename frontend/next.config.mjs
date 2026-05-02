/** @type {import('next').NextConfig} */
const nextConfig = {
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
