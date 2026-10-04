"use client";

import {
  BarChart3,
  Bot,
  CalendarDays,
  CreditCard,
  Dumbbell,
  LayoutDashboard,
  MapPin,
  Settings,
  Target,
  Users,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONS = {
  dashboard: LayoutDashboard,
  reports: BarChart3,
  assistant: Bot,
  schedule: CalendarDays,
  clients: Users,
  leads: Target,
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

  return (
    <nav aria-label={t("label")}>
      <ul className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = ICONS[item.icon];
          return (
            <li key={item.href}>
              <Link
                href={item.href}
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
