import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { Container } from "@/components/layout/container";

const DOCS = ["terms", "privacy", "accessibility"] as const;
type Doc = (typeof DOCS)[number];

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
  const body = t.raw(`${doc as Doc}.body`) as string[];
  return (
    <main className="enter section-y">
      <Container className="grid items-start gap-10 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-16">
        <nav aria-label={t("navLabel")} className="lg:sticky lg:top-24">
          <ul className="flex flex-wrap gap-2 lg:flex-col lg:gap-1">
            {DOCS.map((item) => (
              <li key={item}>
                <Link
                  href={`/legal/${item}`}
                  aria-current={item === doc ? "page" : undefined}
                  className={`block rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                    item === doc ? "bg-primary/10 text-primary" : "text-muted hover:bg-foreground/5 hover:text-foreground"
                  }`}
                >
                  {t(`${item}.title`)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <article className="flex max-w-[44rem] flex-col gap-6">
          <h1 className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">{t(`${doc as Doc}.title`)}</h1>
          <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm font-medium">
            {t("draft")}
          </p>
          {body.map((paragraph) => (
            <p key={paragraph} className="text-lg leading-relaxed">
              {paragraph}
            </p>
          ))}
        </article>
      </Container>
    </main>
  );
}
