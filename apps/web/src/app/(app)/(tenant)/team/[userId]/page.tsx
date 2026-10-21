import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";

import { StaffCardBody } from "./staff-card-body";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("staffCard");
  return { title: `${t("title")} · ${BRAND.name}` };
}

export default async function StaffCardPage({ params, searchParams }: PageProps<"/team/[userId]">) {
  const { userId } = await params;
  const query = await searchParams;
  const t = await getTranslations("team");
  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team" label={t("title")} />
      <StaffCardBody userId={userId} tab={query.tab} />
    </Container>
  );
}
