/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  typescript: {
    // TODO: Fix strict type errors and re-enable
    ignoreBuildErrors: true,
  },
  eslint: {
    // TODO: Fix lint warnings and re-enable
    ignoreDuringBuilds: true,
  },

  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ...config.watchOptions,
        ignored: ["**/.git/**", "**/node_modules/**", "**/.next/**"],
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
};

module.exports = nextConfig;
