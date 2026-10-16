import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";
import { industryOptions, industryTexts } from "@/lib/verticals";

import { Composer, type Initial } from "./composer";

type Announcement = components["schemas"]["Announcement"];

/** The shared page for writing a new message and editing a draft: it loads the choices the
 * audience filters offer (industries, modules and businesses on the platform). */
export async function ComposerPage({ announcement }: { announcement?: Announcement }) {
  const t = await getTranslations();
  const locale = (await getLocale()) === "he" ? "he" : "en";
  const { api } = await getPlatformFor("broadcasts.manage");
  const businesses = unwrap(await api.GET("/platform/businesses"));
  const { text } = industryTexts(t);
  const verticals = industryOptions(text, (name) => t("start.industry.otherKind", { name }));
  const modules = [...new Set(businesses.flatMap((b) => b.modules))].map((key) => ({ value: key, label: t(`modules.names.${key as "client_app"}`) }));
  const initial: Initial | undefined = announcement && {
    id: announcement.id,
    kind: announcement.kind,
    channels: announcement.channels,
    audience: announcement.audience,
    content: announcement.content,
    status: announcement.status,
    scheduled_at: announcement.scheduled_at,
  };

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/platform/broadcasts" className="text-sm font-medium text-primary hover:underline">
        {t("platform.broadcasts.back")}
      </Link>
      <PageHeader title={t("platform.broadcasts.title")} description={t("platform.broadcasts.subtitle")} />
      <Composer
        initial={initial}
        locale={locale}
        verticals={verticals.map(({ value, label }) => ({ value, label }))}
        modules={modules}
        businesses={businesses.map((b) => ({ value: b.id, label: b.name }))}
      />
    </Container>
  );
}
