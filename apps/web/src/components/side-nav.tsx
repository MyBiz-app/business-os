"use client";

import { Activity, BarChart3, Bot, Building2, CalendarDays, ChevronDown, ChevronRight, Clock, FileSignature, FileText, FolderOpen, Globe, Inbox, LayoutDashboard, LayoutGrid, Lock, MapPin, Megaphone, Menu, MessageCircle, Plug, Receipt, ScrollText, Settings, Smartphone, Sparkles, Tags, Target, Truck, TriangleAlert, Users, UsersRound, Wallet } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useId, useState, useSyncExternalStore } from "react";

import { useScrollSpy } from "./use-scroll-spy";

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
  content: Sparkles,
  catalog: Tags,
  sales: Receipt,
  locations: MapPin,
  team: UsersRound,
  settings: Settings,
  businesses: Building2,
  inbox: Inbox,
  billing: Wallet,
  audit: ScrollText,
  health: Activity,
  integrations: Plug,
  broadcasts: Megaphone,
  incidents: TriangleAlert,
  quotes: FileSignature,
  invoices: FileText,
  time: Clock,
  files: FolderOpen,
  migration: Truck,
  website: Globe,
} as const;

export type NavIcon = keyof typeof ICONS;
/** `locked`: a module the business doesn't have; the link opens its preview. */
/** A sub-item: a page of the area, or (`href` with a `#id`) a section of the page the area opens. */
export type NavChild = { href: string; label: string; locked?: boolean };
export type NavItem = { href: string; label: string; icon: NavIcon; locked?: boolean; group?: string; children?: NavChild[] };

const STORAGE_KEY = "crm.nav.open";
const pathOf = (href: string) => href.split("#")[0];
const anchorOf = (href: string) => (href.includes("#") ? href.split("#")[1] : null);

// Which areas the user opened or closed by hand, kept in the browser.
const listeners = new Set<() => void>();
function subscribeChosen(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}
function readChosen() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Smooth scroll to a section, with a short highlight; reduced motion jumps without animating. */
function goToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
  el.setAttribute("data-nav-flash", "");
  window.setTimeout(() => el.removeAttribute("data-nav-flash"), 1500);
  try {
    window.history.replaceState(null, "", `#${id}`);
  } catch {
    // Not critical: the page is already scrolled.
  }
}

export function SideNav({ items, label }: { items: NavItem[]; label?: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  // On small screens the list is a menu that opens below a button showing the current page.
  const [open, setOpen] = useState(false);
  const listId = useId();
  // The most specific match wins (/clients/join over /clients); a sub-page wins a tie with its area.
  const links = items.flatMap((item) => [
    { href: item.href, item, child: false },
    ...(item.children ?? []).filter((c) => !c.href.includes("#")).map((c) => ({ href: c.href, item, child: true })),
  ]);
  const match = links
    .filter((link) => pathname === link.href || pathname.startsWith(`${link.href}/`))
    .sort((a, b) => b.href.length - a.href.length || Number(b.child) - Number(a.child))[0];
  const current = match?.item;
  // Sub-items that differ by a query (`/catalog?tab=plans`): the one named in the address, else the first.
  const params = useSearchParams();
  const queryKids = (current?.children ?? []).filter((c) => c.href.includes("?") && pathOf(c.href.split("?")[0]) === pathname);
  const tab = params.get("tab");
  const queryChild = queryKids.length > 0 ? (queryKids.find((c) => new URLSearchParams(c.href.split("?")[1]).get("tab") === tab) ?? queryKids[0]).href : null;
  const currentChild = queryChild ?? (match?.child ? match.href : null);
  const CurrentIcon = current ? ICONS[current.icon] : Menu;

  // Which areas are unfolded: the one you are in, unless you closed it; others stay as you left them.
  const saved = useSyncExternalStore(subscribeChosen, readChosen, () => "");
  const chosen: Record<string, boolean> = saved ? JSON.parse(saved) : {};
  const toggle = (href: string, now: boolean) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...chosen, [href]: !now }));
    } catch {
      // Storage can be blocked: the menu then follows the current page only.
    }
    for (const listener of listeners) listener();
  };

  // Sections of the open page, for the marker that follows the scroll.
  const anchors = (current?.children ?? []).flatMap((c) => (c.href.includes("#") && pathOf(c.href) === pathname ? [anchorOf(c.href) as string] : []));
  const spied = useScrollSpy(anchors);

  return (
    <nav aria-label={label ?? t("label")}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        className="btn-plain mx-3 mb-3 flex w-[calc(100%-1.5rem)] items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-semibold text-foreground md:hidden"
      >
        <CurrentIcon aria-hidden="true" className="size-[18px] text-electric" />
        <span className="flex-1 text-start">{current?.label ?? t("menu")}</span>
        <span className="sr-only">{t("menu")}</span>
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <ul
        id={listId}
        className={`${open ? "grid" : "hidden"} grid-cols-2 gap-1 px-3 pb-3 md:flex md:flex-col`}
      >
        {items.map((item, index) => {
          const inArea = item.href === current?.href;
          const active = inArea && !currentChild;
          const Icon = ICONS[item.icon];
          const children = item.children ?? [];
          const unfolded = children.length > 0 && (chosen[item.href] ?? inArea);
          const childrenId = `${listId}-${index}`;
          const heading = item.group && item.group !== items[index - 1]?.group ? item.group : null;
          return (
            <li key={item.href} className={unfolded ? "max-md:col-span-2" : undefined}>
              {heading && (
                <p className="mb-1 mt-4 hidden px-3 text-xs font-semibold uppercase tracking-wide text-muted/80 md:block">
                  {heading}
                </p>
              )}
              <div className="relative">
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                aria-label={item.locked ? t("lockedItem", { name: item.label }) : undefined}
                className={`group relative flex items-center gap-3 whitespace-nowrap rounded-xl py-2 ps-3 text-sm ${children.length > 0 ? "pe-10" : "pe-3"} font-medium transition-colors duration-200 ${
                  active
                    ? "bg-primary/20 text-foreground"
                    : inArea
                      ? "text-foreground hover:bg-foreground/5"
                      : item.locked
                      ? "text-muted/80 hover:bg-foreground/5 hover:text-foreground"
                      : "text-muted hover:bg-foreground/5 hover:text-foreground"
                }`}
              >
                {/* Active marker on the inline-start edge (desktop column). */}
                <span
                  aria-hidden="true"
                  className={`absolute inset-y-2 start-0 hidden w-1 rounded-full bg-electric transition-transform duration-300 md:block ${
                    active ? "scale-y-100" : "scale-y-0"
                  }`}
                />
                <Icon
                  aria-hidden="true"
                  className={`size-[18px] shrink-0 transition-transform duration-200 ${active ? "text-electric" : "group-hover:scale-110"}`}
                />
                <span className="truncate">{item.label}</span>
                {item.locked && (
                  <Lock aria-hidden="true" className="ms-auto size-3.5 shrink-0 opacity-70" />
                )}
              </Link>
              {children.length > 0 && (
                <button
                  type="button"
                  aria-expanded={unfolded}
                  aria-controls={childrenId}
                  aria-label={t(unfolded ? "collapse" : "expand", { name: item.label })}
                  onClick={() => toggle(item.href, unfolded)}
                  className="btn-plain absolute inset-y-0 end-1 my-auto flex size-7 items-center justify-center rounded-lg text-muted hover:bg-foreground/10 hover:text-foreground"
                >
                  <ChevronRight aria-hidden="true" className={`size-4 transition-transform duration-200 rtl:-scale-x-100 ${unfolded ? "rotate-90 rtl:-rotate-90" : ""}`} />
                </button>
              )}
              </div>
              {unfolded && (
                <ul id={childrenId} className="enter my-0.5 ms-5 flex flex-col gap-0.5 border-s border-border ps-2">
                  {children.map((child) => {
                    const anchor = anchorOf(child.href);
                    const here = anchor ? pathOf(child.href) === pathname : false;
                    const childActive = anchor ? here && (spied ?? anchors[0]) === anchor : currentChild === child.href;
                    return (
                      <li key={child.href}>
                        <Link
                          href={child.href}
                          scroll={anchor ? false : undefined}
                          onClick={(event) => {
                            setOpen(false);
                            if (anchor && here) {
                              event.preventDefault();
                              goToSection(anchor);
                            }
                          }}
                          aria-current={childActive ? (anchor ? "location" : "page") : undefined}
                          className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors duration-200 ${
                            childActive ? "bg-primary/15 font-semibold text-foreground" : "text-muted hover:bg-foreground/5 hover:text-foreground"
                          }`}
                        >
                          <span className="truncate">{child.label}</span>
                          {child.locked && <Lock aria-hidden="true" className="ms-auto size-3 shrink-0 opacity-70" />}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
