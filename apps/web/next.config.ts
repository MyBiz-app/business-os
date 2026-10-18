import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs/config";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  transpilePackages: ["@business-os/brand", "@business-os/i18n", "@business-os/api-client", "@business-os/verticals"],
  // Client import uploads files up to 2 MB through a server action.
  experimental: { serverActions: { bodySizeLimit: "3mb" } },
  poweredByHeader: false,
  // The Content-Security-Policy (per-request nonce), HSTS and X-Robots-Tag are set in src/proxy.ts.
  // The catalog replaced the services and plans pages; old links and bookmarks still arrive.
  async redirects() {
    return [
      { source: "/services", destination: "/catalog?tab=services", permanent: true },
      { source: "/services/new", destination: "/catalog/services/new", permanent: true },
      { source: "/services/:id", destination: "/catalog/services/:id", permanent: true },
      { source: "/plans", destination: "/catalog?tab=plans", permanent: true },
      { source: "/plans/new", destination: "/catalog/plans/new", permanent: true },
      { source: "/plans/:id", destination: "/catalog/plans/:id", permanent: true },
    ];
  },
  async headers() {
    return [
      {
        // Everything except /embed/: those pages are made to be framed by other sites (the CSP
        // frame-ancestors in src/proxy.ts decides, and X-Frame-Options would override it).
        source: "/((?!embed/).*)",
        headers: [{ key: "X-Frame-Options", value: "DENY" }],
      },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

const config = withNextIntl(nextConfig);

// Source maps are uploaded to Sentry (readable stack traces) only in a build that has an auth
// token; without SENTRY_AUTH_TOKEN the build is exactly as before.
export default process.env.SENTRY_AUTH_TOKEN
  ? // The organisation, project and token come from SENTRY_ORG, SENTRY_PROJECT and SENTRY_AUTH_TOKEN.
    withSentryConfig(config, { sourcemaps: { deleteSourcemapsAfterUpload: true } })
  : config;
