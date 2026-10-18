import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { ReactNode } from "react";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

/** The page around a catalog form, when it is opened directly (a shared link or a refresh) and
 * not as a window over the list. */
export async function CatalogPage({ title, backHref, children }: { title: ReactNode; backHref: string; children: ReactNode }) {
  const t = await getTranslations("common");
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href={backHref} className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <PageHeader title={title} />
      {children}
    </Container>
  );
}
