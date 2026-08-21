import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const nextConfig = {
  devIndicators: false,
  outputFileTracingRoot: __dirname,
  async rewrites() {
    if (!apiBaseUrl) {
      return [];
    }

    return [
      {
        source: "/chat",
        destination: `${apiBaseUrl}/chat`,
      },
      {
        source: "/chatkit",
        destination: `${apiBaseUrl}/chatkit`,
      },
      {
        source: "/chatkit/:path*",
        destination: `${apiBaseUrl}/chatkit/:path*`,
      },
    ];
  },
};

export default nextConfig;
