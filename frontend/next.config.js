/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone", // small Docker runtime image
  reactStrictMode: true,
};
module.exports = nextConfig;
