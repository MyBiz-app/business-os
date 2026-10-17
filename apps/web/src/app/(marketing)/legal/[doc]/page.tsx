import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { Container } from "@/components/layout/container";
import { PrintButton } from "@/components/marketing/print-button";

const DOCS = ["terms", "privacy", "accessibility"] as const;
type Doc = (typeof DOCS)[number];

/** Date of the last content change of the legal copy (ISO). Bump it whenever the texts change. */
const UPDATED_ON = "2026-10-17";

type Section = { id: string; title: string; p: string[]; items?: string[] };

export function generateStaticParams() {
  return DOCS.map((doc) => ({ doc }));
}

export async function generateMetadata({ params }: PageProps<"/legal/[doc]">): Promise<Metadata> {
  const { doc } = await params;
  if (!DOCS.includes(doc as Doc)) return {};
  const t = await getTranslations("marketing.legal");
  return { title: `${t(`${doc as Doc}.title`)} · ${BRAND.name}` };
}

/** Terms, privacy and accessibility: drafts until legal review before launch. */
export default async function LegalPage({ params }: PageProps<"/legal/[doc]">) {
  const { doc } = await params;
  if (!DOCS.includes(doc as Doc)) notFound();
  const t = await getTranslations("marketing.legal");
  const locale = await getLocale();
  const title = t(`${doc as Doc}.title`);
  const intro = t(`${doc as Doc}.intro`);
  const sections = t.raw(`${doc as Doc}.sections`) as Section[];
  const updated = new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(new Date(UPDATED_ON));
  return (
    <main id="main" className="enter section-y">
      <Container className="grid items-start gap-10 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-16">
        <div className="flex flex-col gap-8 print:hidden lg:sticky lg:top-24">
          <nav aria-label={t("navLabel")}>
            <ul className="flex flex-wrap gap-2 lg:flex-col lg:gap-1">
              {DOCS.map((item) => (
                <li key={item}>
                  <Link
                    href={`/legal/${item}`}
                    aria-current={item === doc ? "page" : undefined}
                    className={`block rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                      item === doc ? "bg-primary/10 text-primary-ink" : "text-muted hover:bg-foreground/5 hover:text-foreground"
                    }`}
                  >
                    {t(`${item}.title`)}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label={t("toc")} className="hidden lg:block">
            <p className="mb-2 px-4 text-xs font-bold uppercase tracking-wide text-muted">{t("toc")}</p>
            <ol className="flex max-h-[50vh] flex-col gap-0.5 overflow-y-auto">
              {sections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="block rounded-lg px-4 py-1.5 text-sm text-muted transition-colors hover:bg-foreground/5 hover:text-foreground"
                  >
                    {index + 1}. {section.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        </div>
        <article className="flex max-w-[44rem] flex-col gap-6">
          <header className="flex flex-col gap-3">
            <h1 className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">{title}</h1>
            <p className="text-sm text-muted">{t("updated", { date: updated })}</p>
            <PrintButton label={t("print")} />
          </header>
          <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm font-medium">
            {t("draft")}
          </p>
          <p className="text-lg leading-relaxed">{intro}</p>
          <nav aria-label={t("toc")} className="rounded-2xl border border-border p-5 lg:hidden print:hidden">
            <p className="mb-2 text-sm font-bold">{t("toc")}</p>
            <ol className="flex flex-col gap-1 text-sm">
              {sections.map((section, index) => (
                <li key={section.id}>
                  <a href={`#${section.id}`} className="text-primary-ink hover:underline">
                    {index + 1}. {section.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
          {sections.map((section, index) => (
            <section key={section.id} id={section.id} aria-labelledby={`${section.id}-h`} className="flex scroll-mt-24 flex-col gap-3">
              <h2 id={`${section.id}-h`} className="text-xl font-bold tracking-tight">
                {index + 1}. {section.title}
              </h2>
              {section.p.map((paragraph) => (
                <p key={paragraph} className="text-base leading-relaxed">
                  {paragraph}
                </p>
              ))}
              {section.items ? (
                <ul className="list-disc space-y-1.5 ps-6 text-base leading-relaxed marker:text-primary-ink">
                  {section.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </article>
      </Container>
    </main>
  );
}
