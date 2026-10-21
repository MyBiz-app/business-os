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
import { type ReactNode, useEffect, useRef, useState } from "react";

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
  // The groups of the open topic page, listed under its item and followed as the page scrolls.
  const content = useRef<HTMLDivElement>(null);
  const [groups, setGroups] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => {
    const element = content.current;
    if (!element || isIndex) return;
    const read = () => {
      const next = Array.from(element.querySelectorAll<HTMLElement>("[data-settings-group][id]")).map((group) => ({
        id: group.id,
        title: group.querySelector("h3")?.textContent?.trim() || group.id,
      }));
      setGroups((now) => (JSON.stringify(now) === JSON.stringify(next) ? now : next));
    };
    read();
    // Content that streams in, and the swap between topics, change what is on the page.
    const observer = new MutationObserver(read);
    observer.observe(element, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      setGroups([]);
    };
  }, [isIndex, pathname]);

  const menu: SectionNavItem[] = items.flatMap((item) => {
    const Icon = ICONS[item.key];
    const inline = (INLINE_TOPICS as readonly TopicKey[]).includes(item.key);
    const isCurrent = !isIndex && current?.key === item.key;
    const topic: SectionNavItem = {
      id: item.key,
      label: t(`nav.items.${item.key}`),
      icon: <Icon aria-hidden="true" className="size-4 shrink-0" />,
      group: t(`nav.groups.${item.group}`),
      href: inline && isIndex ? undefined : inline ? `/settings#${item.key}` : item.href,
      current: isCurrent,
    };
    const sections: SectionNavItem[] = isCurrent ? groups.map((group) => ({ id: group.id, label: group.title, nested: true })) : [];
    return [topic, ...sections];
  });

  return (
    <>
      <PageHeader title={title} description={description} className="print:hidden" />
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start lg:gap-6 xl:gap-10">
        <SectionNav items={menu} label={t("nav.label")} />
        <div ref={content} className="@container flex min-w-0 flex-col gap-4">
          <ContentSwap swapKey={isIndex ? "index" : (current?.key ?? "index")}>{children}</ContentSwap>
        </div>
      </div>
    </>
  );
}
