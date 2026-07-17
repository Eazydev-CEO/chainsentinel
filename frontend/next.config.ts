import type { NextConfig } from "next";

// Server-side URL for reaching Django (docker: http://backend:8212).
const API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://localhost:8212";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Django API routes end in "/" — without this, Next 308-redirects them to
  // the slashless form BEFORE the /api rewrite runs, breaking POST requests.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Same-origin API in development: the browser talks to Next, Next proxies
    // to Django, cookies stay first-party. In production nginx routes /api
    // directly to Django and this rewrite is simply never hit.
    // The destination ends in "/" because :path* drops trailing slashes and
    // Django's URLs require them (POST bodies can't survive APPEND_SLASH).
    return [
      {
        source: "/api/:path*/",
        destination: `${API_INTERNAL_URL}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*/`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
