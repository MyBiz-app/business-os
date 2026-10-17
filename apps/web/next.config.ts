import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  transpilePackages: ["@business-os/brand", "@business-os/i18n", "@business-os/api-client", "@business-os/verticals"],
  // Client import uploads files up to 2 MB through a server action.
  experimental: { serverActions: { bodySizeLimit: "3mb" } },
  poweredByHeader: false,
  // The Content-Security-Policy (per-request nonce), HSTS and X-Robots-Tag are set in src/proxy.ts.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
