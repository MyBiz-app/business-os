"use client";

import {
  BarChart3,
  Bot,
  CalendarDays,
  ChevronDown,
  CreditCard,
  Dumbbell,
  LayoutDashboard,
  MapPin,
  Menu,
  MessageCircle,
  Settings,
  Target,
  Users,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const ICONS = {
  dashboard: LayoutDashboard,
  reports: BarChart3,
  assistant: Bot,
  schedule: CalendarDays,
  clients: Users,
  leads: Target,
  messages: MessageCircle,
  services: Dumbbell,
  plans: CreditCard,
  locations: MapPin,
  team: UsersRound,
  settings: Settings,
} as const;

export type NavIcon = keyof typeof ICONS;
export type NavItem = { href: string; label: string; icon: NavIcon };

export function SideNav({ items }: { items: NavItem[] }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  // On small screens the list is a menu that opens below a button showing the current page.
  const [open, setOpen] = useState(false);
  const current = items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const CurrentIcon = current ? ICONS[current.icon] : Menu;

  return (
    <nav aria-label={t("label")}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls="main-nav-list"
        onClick={() => setOpen((value) => !value)}
        className="mx-3 mb-3 flex w-[calc(100%-1.5rem)] items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-semibold md:hidden"
      >
        <CurrentIcon aria-hidden="true" className="size-[18px] text-primary" />
        <span className="flex-1 text-start">{current?.label ?? t("menu")}</span>
        <span className="sr-only">{t("menu")}</span>
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <ul
        id="main-nav-list"
        className={`${open ? "grid" : "hidden"} grid-cols-2 gap-1 px-3 pb-3 md:flex md:flex-col`}
      >
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = ICONS[item.icon];
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`group relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                  active
                    ? "bg-primary/10 text-primary"
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
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
