import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  transpilePackages: ["@business-os/i18n", "@business-os/api-client"],
};

export default withNextIntl(nextConfig);
