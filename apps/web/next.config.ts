import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  transpilePackages: ["@business-os/i18n", "@business-os/api-client"],
  // Client import uploads files up to 2 MB through a server action.
  experimental: { serverActions: { bodySizeLimit: "3mb" } },
};

export default withNextIntl(nextConfig);
