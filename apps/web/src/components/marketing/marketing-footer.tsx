import { categories } from "@business-os/verticals";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { AppStoresStrip } from "@/components/marketing/app-stores-strip";
import { ShowAccessibilityButton } from "@/components/marketing/show-accessibility-button";
import { SocialIcon } from "@/components/marketing/social-icons";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { statusPageUrl } from "@/lib/status";
import { socialLinks } from "@/lib/social";
import { industryTexts } from "@/lib/verticals";

export async function MarketingFooter() {
  const t = await getTranslations("marketing");
  const tApp = await getTranslations("app");
  const { text } = industryTexts(await getTranslations());
  const statusUrl = statusPageUrl();
  const columns = [
    {
      title: t("footer.product"),
      links: [
        { href: "/features", label: t("nav.features") },
        { href: "/pricing", label: t("nav.pricing") },
        { href: "/login", label: t("nav.login") },
        { href: "/start", label: t("nav.start") },
        { href: "/getting-started", label: t("nav.guide") },
      ],
    },
    {
      title: t("nav.industries"),
      links: [
        ...categories()
          .filter((c) => c.status !== "planned")
          .map(({ key }) => ({ href: `/industries/${key}`, label: text(key, "name") })),
        { href: "/industries", label: t("industries.all") },
      ],
    },
    {
      title: t("footer.company"),
      links: [
        { href: "/about", label: t("nav.about") },
        { href: "/contact", label: t("nav.contact") },
        ...(statusUrl ? [{ href: statusUrl, label: t("footer.status") }] : []),
      ],
    },
    {
      title: t("footer.legal"),
      links: [
        { href: "/legal/terms", label: t("footer.terms") },
        { href: "/legal/privacy", label: t("footer.privacy") },
        { href: "/legal/accessibility", label: t("footer.accessibility") },
      ],
    },
  ];
  const social = socialLinks();
  return (
    <footer className="bg-navy text-white">
      <Container className="grid grid-cols-2 gap-x-6 gap-y-8 py-14 md:grid-cols-[1.5fr_repeat(4,1fr)] md:gap-10 lg:py-16">
        <div className="col-span-2 flex flex-col gap-3 md:col-span-1">
          <span className="flex items-center gap-2 text-lg font-bold">
            <BrandMark className="size-8" />
            {tApp("name")}
          </span>
          <p className="max-w-xs text-sm text-white/65">{t("footer.tagline")}</p>
          {social.length > 0 && (
            <ul aria-label={t("footer.social")} className="mt-2 flex flex-wrap gap-2">
              {social.map(({ key, label, url }) => (
                <li key={key}>
                  <a href={url} target="_blank" rel="noopener noreferrer" aria-label={label} title={label} className="flex size-9 items-center justify-center rounded-full border border-white/20 text-white/80 transition-colors hover:border-electric hover:text-white">
                    <SocialIcon name={key} className="size-4" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
        {columns.map((column) => (
          <nav key={column.title} aria-label={column.title} className="flex flex-col gap-2 text-sm">
            <h2 className="font-semibold text-white">{column.title}</h2>
            {column.links.map((link) => (
              <Link key={link.href} href={link.href} className="text-white/65 transition-colors hover:text-white">
                {link.label}
              </Link>
            ))}
          </nav>
        ))}
      </Container>
      <AppStoresStrip />
      <div className="border-t border-white/10">
        <Container className="flex flex-wrap items-center justify-between gap-4 py-5">
          <p className="text-xs text-white/50">{t("footer.rights", { year: new Date().getFullYear() })}</p>
          <ShowAccessibilityButton />
          <ThemeToggle className="!border-white/20 !bg-white/5 !text-white/80 hover:!bg-white/10 hover:!text-white" />
        </Container>
      </div>
    </footer>
  );
}
