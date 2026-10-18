"use client";

import {
  Building2,
  ChevronLeft,
  CreditCard,
  Database,
  History,
  LifeBuoy,
  type LucideIcon,
  Palette,
  Plug,
  Puzzle,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useLayoutEffect } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { ContentSwap } from "@/components/ui/content-swap";

import type { TopicGroup, TopicKey } from "./topics";

const ICONS: Record<TopicKey, LucideIcon> = {
  business: Building2,
  branding: Palette,
  modules: Puzzle,
  billing: CreditCard,
  integrations: Plug,
  audit: History,
  data: Database,
  help: LifeBuoy,
};

type Item = { key: TopicKey; href: string; group: TopicGroup };

/** The room's frame. Desktop: a sticky menu beside the topic. Phone: the menu is the page at
 * `/settings` and a topic opens with a way back. */
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
  const groups = [...new Set(items.map((item) => item.group))];

  return (
    <>
      <PageHeader title={title} description={description} className="print:hidden" />
      <div className="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start xl:gap-10">
        <nav
          aria-label={t("nav.label")}
          className={`${isIndex ? "" : "hidden lg:block"} flex flex-col gap-5 print:hidden lg:sticky lg:top-24`}
        >
          {groups.map((group) => (
            <div key={group} className="flex flex-col gap-1">
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-muted">{t(`nav.groups.${group}`)}</p>
              <ul className="flex flex-col gap-0.5">
                {items
                  .filter((item) => item.group === group)
                  .map((item) => {
                    const Icon = ICONS[item.key];
                    const active = current?.key === item.key;
                    return (
                      <li key={item.key}>
                        <Link
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                            active ? "bg-primary/10 font-semibold text-foreground" : "text-foreground hover:bg-foreground/5"
                          }`}
                        >
                          <Icon aria-hidden="true" className="size-4 shrink-0" />
                          <span className="flex-1">{t(`nav.items.${item.key}`)}</span>
                          <ChevronLeft aria-hidden="true" className="size-4 text-muted lg:hidden ltr:rotate-180" />
                        </Link>
                      </li>
                    );
                  })}
              </ul>
            </div>
          ))}
        </nav>
        <div className={`${isIndex ? "hidden lg:block" : ""} flex min-w-0 flex-col gap-4`}>
          {!isIndex && (
            <Link href="/settings" className="inline-flex items-center gap-1 text-sm text-primary-ink underline-offset-4 hover:underline print:hidden lg:hidden">
              <ChevronLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
              {t("nav.back")}
            </Link>
          )}
          <ContentSwap swapKey={current?.key ?? "index"}>{children}</ContentSwap>
        </div>
      </div>
    </>
  );
}

/** `/settings` itself: on a phone the menu is the page; on a wide screen it opens the first topic. */
export function OpenFirstTopicOnDesktop({ href }: { href: string }) {
  const router = useRouter();
  useLayoutEffect(() => {
    if (window.matchMedia("(min-width: 64rem)").matches) router.replace(href);
  }, [router, href]);
  return null;
}
