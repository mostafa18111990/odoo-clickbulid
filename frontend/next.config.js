const createNextIntlPlugin = require("next-intl/plugin");
const withNextIntl = createNextIntlPlugin();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://clickbuild.com/api/v1",
    NEXT_PUBLIC_DOMAIN:  process.env.NEXT_PUBLIC_DOMAIN  || "clickbuild.com",
  },
};

module.exports = withNextIntl(nextConfig);
