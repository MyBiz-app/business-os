"use client";

import {
  BarChart3,
  Building2,
  Inbox,
  Plug,
  ScrollText,
  Wallet,
  Bot,
  CalendarDays,
  ChevronDown,
  CreditCard,
  Dumbbell,
  LayoutDashboard,
  LayoutGrid,
  Lock,
  MapPin,
  Menu,
  Receipt,
  MessageCircle,
  Settings,
  Smartphone,
  Target,
  Users,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";

const ICONS = {
  dashboard: LayoutDashboard,
  reports: BarChart3,
  assistant: Bot,
  schedule: CalendarDays,
  resources: LayoutGrid,
  clients: Users,
  clientApp: Smartphone,
  leads: Target,
  messages: MessageCircle,
  services: Dumbbell,
  plans: CreditCard,
  sales: Receipt,
  locations: MapPin,
  team: UsersRound,
  settings: Settings,
  businesses: Building2,
  inbox: Inbox,
  billing: Wallet,
  audit: ScrollText,
  integrations: Plug,
} as const;

export type NavIcon = keyof typeof ICONS;
/** `locked`: a module the business doesn't have; the link opens its preview. */
export type NavItem = { href: string; label: string; icon: NavIcon; locked?: boolean };

export function SideNav({ items, label }: { items: NavItem[]; label?: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  // On small screens the list is a menu that opens below a button showing the current page.
  const [open, setOpen] = useState(false);
  const listId = useId();
  // The most specific match wins (/clients/join over /clients).
  const current = items
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
  const CurrentIcon = current ? ICONS[current.icon] : Menu;

  return (
    <nav aria-label={label ?? t("label")}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        className="mx-3 mb-3 flex w-[calc(100%-1.5rem)] items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-semibold md:hidden"
      >
        <CurrentIcon aria-hidden="true" className="size-[18px] text-primary" />
        <span className="flex-1 text-start">{current?.label ?? t("menu")}</span>
        <span className="sr-only">{t("menu")}</span>
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <ul
        id={listId}
        className={`${open ? "grid" : "hidden"} grid-cols-2 gap-1 px-3 pb-3 md:flex md:flex-col`}
      >
        {items.map((item) => {
          const active = item.href === current?.href;
          const Icon = ICONS[item.icon];
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                aria-label={item.locked ? t("lockedItem", { name: item.label }) : undefined}
                className={`group relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                  active
                    ? "bg-primary/10 text-primary"
                    : item.locked
                      ? "text-muted/80 hover:bg-foreground/5 hover:text-foreground"
                      : "text-muted hover:bg-foreground/5 hover:text-foreground"
                }`}
              >
                {/* Active marker on the inline-start edge (desktop column). */}
                <span
                  aria-hidden="true"
                  className={`absolute inset-y-2 start-0 hidden w-1 rounded-full bg-primary transition-transform duration-300 md:block ${
                    active ? "scale-y-100" : "scale-y-0"
                  }`}
                />
                <Icon
                  aria-hidden="true"
                  className={`size-[18px] shrink-0 transition-transform duration-200 ${active ? "" : "group-hover:scale-110"}`}
                />
                <span className="truncate">{item.label}</span>
                {item.locked && (
                  <Lock aria-hidden="true" className="ms-auto size-3.5 shrink-0 opacity-70" />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
