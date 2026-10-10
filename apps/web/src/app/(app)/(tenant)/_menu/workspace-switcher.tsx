"use client";

import { Check, ChevronsUpDown, LayoutGrid, Layers, Loader2, Plus, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useId, useRef, useState, useTransition } from "react";

import { moveFocus, useDismiss } from "@/components/use-dismiss";
import { branchColor } from "@/lib/calendar";

import { switchBranch, switchBusiness } from "./actions";

type Props = {
  name: string;
  logo: string | null;
  current: string;
  memberships: { tenant_id: string; tenant_name: string }[];
  branches: { id: string; name: string }[];
  /** The current branch, or null for all of them. */
  branch: string | null;
};

const SEARCH_FROM = 8;

/** The business ("network") and branch at the top of the side menu, in one popover: the open
 * business with its branches (each in the color it has in the calendar and reports), then the
 * person's other businesses. Long lists get a search field. */
export function WorkspaceSwitcher({ name, logo, current, memberships, branches, branch }: Props) {
  const t = useTranslations("businessMenu");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pending, start] = useTransition();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);
  useDismiss(open, close, root, button);

  const multi = branches.length > 1;
  const others = memberships.filter((m) => m.tenant_id !== current);
  const searchable = branches.length + others.length >= SEARCH_FROM;
  const matches = (text: string) => text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  const shownBranches = branches.map((b, index) => ({ ...b, index })).filter((b) => matches(b.name));
  const shownOthers = others.filter((m) => matches(m.tenant_name));
  const currentIndex = branches.findIndex((b) => b.id === branch);

  const run = (action: (data: FormData) => Promise<void>, field: string, value: string) => {
    const data = new FormData();
    data.set(field, value);
    close();
    button.current?.focus();
    start(() => action(data));
  };

  const option =
    "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-start text-sm outline-none transition-colors hover:bg-foreground/5 focus-visible:bg-foreground/5 aria-[current=true]:font-semibold";
  return (
    <div ref={root} className="relative mx-3 my-3">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-busy={pending}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
            requestAnimationFrame(() => document.getElementById(panelId)?.querySelector<HTMLElement>("input, button, a")?.focus());
          }
        }}
        className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-start transition-colors hover:bg-background/70 aria-expanded:bg-background/70"
      >
        {logo ? (
          <Image src={logo} alt="" width={40} height={40} unoptimized className="size-10 shrink-0 rounded-xl object-contain shadow-sm" />
        ) : (
          <span aria-hidden="true" className="btn-primary size-10 shrink-0 text-lg">
            {name.slice(0, 1)}
          </span>
        )}
        <span className="flex min-w-0 flex-1 flex-col">
          <span dir="auto" className="truncate font-semibold">
            {name}
          </span>
          {multi && (
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <span
                aria-hidden="true"
                className="size-2 shrink-0 rounded-full"
                style={{
                  background: currentIndex >= 0 ? branchColor(currentIndex) : "var(--muted)",
                }}
              />
              <span dir="auto" className="truncate">
                {currentIndex >= 0 ? branches[currentIndex].name : t("allBranches")}
              </span>
            </span>
          )}
        </span>
        {pending ? (
          <Loader2 aria-hidden="true" className="size-4 shrink-0 animate-spin text-muted motion-reduce:animate-none" />
        ) : (
          <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-muted" />
        )}
        <span className="sr-only">{t("switch")}</span>
      </button>

      <div
        id={panelId}
        role="dialog"
        aria-label={t("switch")}
        data-open={open}
        onKeyDown={(event) => moveFocus(event, "input, [data-item]")}
        className="popover absolute inset-x-0 top-full z-40 mt-1 flex max-h-[min(70dvh,34rem)] flex-col overflow-hidden md:-inset-x-1"
      >
        {searchable && (
          <label className="flex items-center gap-2 border-b border-border px-3 py-2.5">
            <Search aria-hidden="true" className="size-4 text-muted" />
            <span className="sr-only">{t("search")}</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("search")}
              className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
            />
          </label>
        )}
        <div className="flex flex-col gap-3 overflow-y-auto p-1.5">
          {multi && (
            <section aria-labelledby={`${panelId}-branches`} className="flex flex-col">
              <h3 id={`${panelId}-branches`} dir="auto" className="truncate px-2.5 pb-1 pt-1.5 text-xs font-semibold text-muted">
                {t("branchesOf", { name })}
              </h3>
              <ul className="relative flex flex-col before:absolute before:inset-y-3 before:start-[1.0625rem] before:w-px before:bg-border">
                {!query && (
                  <li>
                    <button type="button" data-item aria-current={branch === null} onClick={() => run(switchBranch, "branch_id", "")} className={option}>
                      <Layers aria-hidden="true" className="relative size-4 shrink-0 bg-surface text-muted" />
                      <span className="flex-1">{t("allBranches")}</span>
                      {branch === null && <Check aria-hidden="true" className="size-4 text-primary" />}
                    </button>
                  </li>
                )}
                {shownBranches.map((b) => (
                  <li key={b.id}>
                    <button type="button" data-item aria-current={b.id === branch} onClick={() => run(switchBranch, "branch_id", b.id)} className={option}>
                      <span
                        aria-hidden="true"
                        className="relative mx-1 size-2 shrink-0 rounded-full ring-4 ring-surface"
                        style={{ background: branchColor(b.index) }}
                      />
                      <span dir="auto" className="flex-1 truncate">
                        {b.name}
                      </span>
                      {b.id === branch && <Check aria-hidden="true" className="size-4 text-primary" />}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {shownOthers.length > 0 && (
            <section aria-labelledby={`${panelId}-others`} className="flex flex-col">
              <h3 id={`${panelId}-others`} className="px-2.5 pb-1 pt-1.5 text-xs font-semibold text-muted">
                {multi ? t("otherBusinesses") : t("myBusinesses")}
              </h3>
              <ul className="flex flex-col">
                {shownOthers.map((m) => (
                  <li key={m.tenant_id}>
                    <button type="button" data-item onClick={() => run(switchBusiness, "tenant_id", m.tenant_id)} className={option}>
                      <span aria-hidden="true" className="grid size-6 shrink-0 place-items-center rounded-md bg-foreground/8 text-xs font-semibold">
                        {m.tenant_name.slice(0, 1)}
                      </span>
                      <span dir="auto" className="flex-1 truncate">
                        {m.tenant_name}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {query && shownBranches.length + shownOthers.length === 0 && <p className="px-2.5 py-3 text-sm text-muted">{t("noMatches")}</p>}
        </div>
        <div className="flex flex-col border-t border-border p-1.5">
          <Link href="/businesses" data-item onClick={close} className={option}>
            <LayoutGrid aria-hidden="true" className="size-4 text-muted" />
            {t("allBusinesses")}
          </Link>
          <Link href="/onboarding" data-item onClick={close} className={`${option} font-medium text-primary`}>
            <Plus aria-hidden="true" className="size-4" />
            {t("newBusiness")}
          </Link>
        </div>
      </div>
    </div>
  );
}
