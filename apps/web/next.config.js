/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config, { isServer }) => {
    // Ignore .git directory changes to prevent cache corruption on Windows
    // when git commits trigger the file watcher during compilation
    config.watchOptions = {
      ...config.watchOptions,
      ignored: /[\\/]\.git[\\/]/,
    };
    return config;
  },
};

module.exports = nextConfig;