"use client";

import {
  Building2,
  CalendarClock,
  CreditCard,
  Database,
  History,
  LifeBuoy,
  type LucideIcon,
  Palette,
  Plug,
  Puzzle,
  Snowflake,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SectionNav, type SectionNavItem } from "@/components/section-nav";
import { PageHeader } from "@/components/layout/page-header";
import { ContentSwap } from "@/components/ui/content-swap";

import type { TopicGroup, TopicKey } from "./topics";

const ICONS: Record<TopicKey, LucideIcon> = {
  business: Building2,
  memberships: Snowflake,
  bookings: CalendarClock,
  branding: Palette,
  modules: Puzzle,
  billing: CreditCard,
  integrations: Plug,
  aiConnections: Sparkles,
  audit: History,
  data: Database,
  help: LifeBuoy,
};

type Item = { key: TopicKey; href: string; group: TopicGroup };

/** Topics shown as sections of the `/settings` page (see `page.tsx`); the rest open as pages of their own. */
export const INLINE_TOPICS = ["business", "memberships", "bookings", "branding", "modules", "integrations", "aiConnections", "data", "help"] as const satisfies readonly TopicKey[];

/** The room's frame: one inner menu. On `/settings` a click scrolls to that topic's section on the
 * same page; topics with a page of their own (billing, audit), and the topic pages reached by a
 * direct link, open as normal links. */
export function SettingsRoom({
  items,
  title,
  description,
  children,
}: {
  items: Item[];
  title: string;
  description: string;
  children: ReactNode;
}) {
  const t = useTranslations("settings");
  const pathname = usePathname();
  const isIndex = pathname === "/settings";
  const current = items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const menu: SectionNavItem[] = items.map((item) => {
    const Icon = ICONS[item.key];
    const inline = (INLINE_TOPICS as readonly TopicKey[]).includes(item.key);
    return {
      id: item.key,
      label: t(`nav.items.${item.key}`),
      icon: <Icon aria-hidden="true" className="size-4 shrink-0" />,
      group: t(`nav.groups.${item.group}`),
      href: inline && isIndex ? undefined : inline ? `/settings#${item.key}` : item.href,
      current: !isIndex && current?.key === item.key,
    };
  });

  return (
    <>
      <PageHeader title={title} description={description} className="print:hidden" />
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start lg:gap-6 xl:gap-10">
        <SectionNav items={menu} label={t("nav.label")} />
        <div className="@container flex min-w-0 flex-col gap-4">
          <ContentSwap swapKey={isIndex ? "index" : (current?.key ?? "index")}>{children}</ContentSwap>
        </div>
      </div>
    </>
  );
}
