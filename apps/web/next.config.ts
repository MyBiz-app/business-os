import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

import { enforcedCsp } from "./src/lib/csp";

const withNextIntl = createNextIntlPlugin();

// The enforced policy still allows inline scripts; the strict nonce-based one runs alongside it as
// Report-Only, set per request by src/proxy.ts. See src/lib/csp.ts.
const isDev = process.env.NODE_ENV !== "production";
const contentSecurityPolicy = enforcedCsp({ dev: isDev });

const nextConfig: NextConfig = {
  transpilePackages: ["@business-os/brand", "@business-os/i18n", "@business-os/api-client", "@business-os/verticals"],
  // Client import uploads files up to 2 MB through a server action.
  experimental: { serverActions: { bodySizeLimit: "3mb" } },
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
          // HTTPS only, for two years. Vercel adds this on its own domain; this covers a custom one.
          ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=63072000" }]),
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
