import { Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

export async function MarketingFooter() {
  const t = await getTranslations("marketing");
  const tApp = await getTranslations("app");
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
      links: (["fitness", "beauty", "clinic", "garage"] as const).map((key) => ({
        href: `/industries/${key}`,
        label: t(`industries.items.${key}.name`),
      })),
    },
    {
      title: t("footer.company"),
      links: [
        { href: "/about", label: t("nav.about") },
        { href: "/contact", label: t("nav.contact") },
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
  return (
    <footer className="border-t border-border bg-surface/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:grid-cols-[1.5fr_repeat(4,1fr)]">
        <div className="flex flex-col gap-3">
          <span className="flex items-center gap-2 text-lg font-bold">
            <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white">
              <Sparkles className="size-4" />
            </span>
            {tApp("name")}
          </span>
          <p className="max-w-xs text-sm text-muted">{t("footer.tagline")}</p>
        </div>
        {columns.map((column) => (
          <nav key={column.title} aria-label={column.title} className="flex flex-col gap-2 text-sm">
            <h2 className="font-semibold">{column.title}</h2>
            {column.links.map((link) => (
              <Link key={link.href} href={link.href} className="text-muted transition-colors hover:text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>
      <p className="border-t border-border px-6 py-5 text-center text-xs text-muted">
        {t("footer.rights", { year: new Date().getFullYear() })}
      </p>
    </footer>
  );
}
