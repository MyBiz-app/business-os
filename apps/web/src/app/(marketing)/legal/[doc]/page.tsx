import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

const DOCS = ["terms", "privacy", "accessibility"] as const;
type Doc = (typeof DOCS)[number];

export function generateStaticParams() {
  return DOCS.map((doc) => ({ doc }));
}

export async function generateMetadata({ params }: PageProps<"/legal/[doc]">): Promise<Metadata> {
  const { doc } = await params;
  if (!DOCS.includes(doc as Doc)) return {};
  const t = await getTranslations("marketing.legal");
  return { title: `${t(`${doc as Doc}.title`)} · MyBiz` };
}

/** Terms, privacy and accessibility: drafts until legal review before launch. */
export default async function LegalPage({ params }: PageProps<"/legal/[doc]">) {
  const { doc } = await params;
  if (!DOCS.includes(doc as Doc)) notFound();
  const t = await getTranslations("marketing.legal");
  const body = t.raw(`${doc as Doc}.body`) as string[];
  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-16">
      <h1 className="text-4xl font-extrabold tracking-tight">{t(`${doc as Doc}.title`)}</h1>
      <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm font-medium">
        {t("draft")}
      </p>
      {body.map((paragraph) => (
        <p key={paragraph} className="text-lg leading-relaxed">
          {paragraph}
        </p>
      ))}
    </main>
  );
}
