"use client";

import { CalendarDays, Clock, CornerDownRight, FileText, Plus, Search, Target, Users, UsersRound, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useState, useSyncExternalStore } from "react";

import { searchEverything } from "@/app/(app)/(tenant)/_menu/search-actions";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { type HitKind, matches, MIN_SEARCH_LENGTH, type PaletteHit, parseRecents, type QuickAction, withRecent } from "@/lib/command-palette";

export type PalettePage = { href: string; label: string };

const KIND_ICONS: Record<HitKind, LucideIcon> = { client: Users, lead: Target, staff: UsersRound, session: CalendarDays, invoice: FileText };
const KIND_ORDER: HitKind[] = ["client", "lead", "staff", "session", "invoice"];
const DEBOUNCE_MS = 220;
const PAGES_SHOWN = 6;

type Section = "recent" | "actions" | HitKind | "pages";
type Row = { id: string; section: Section; label: string; meta?: string; href: string; icon: LucideIcon; hit?: PaletteHit };

const recentsKey = (tenantId: string) => `crm.recents.${tenantId}`;

function readRecents(tenantId: string): PaletteHit[] {
  try {
    return parseRecents(window.localStorage.getItem(recentsKey(tenantId)));
  } catch {
    return [];
  }
}

function rememberRecent(tenantId: string, hit: PaletteHit) {
  try {
    window.localStorage.setItem(recentsKey(tenantId), JSON.stringify(withRecent(readRecents(tenantId), hit)));
  } catch {
    // Storage can be blocked: the list of recent records just stays empty.
  }
}

const noSubscription = () => () => {};
const isApplePlatform = () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

/** Search and quick actions (Cmd+K / Ctrl+K). The button sits in the side menu: a search field on a
 * computer, a magnifier on a phone. The window finds records through the API (which keeps it to what
 * the person may open), and offers the pages and the quick actions they may use. */
export function CommandPalette({ tenantId, pages, actions }: { tenantId: string; pages: PalettePage[]; actions: QuickAction[] }) {
  const t = useTranslations("commandPalette");
  const [open, setOpen] = useState(false);
  const apple = useSyncExternalStore(noSubscription, isApplePlatform, () => false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <Button
        variant="plain"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-keyshortcuts="Control+K Meta+K"
        aria-label={t("open")}
        className="mx-3 mb-3 flex items-center gap-2 rounded-xl border border-border bg-background/60 px-3 py-2 text-sm text-muted transition-colors hover:text-foreground max-md:mb-0 max-md:me-3 max-md:ms-0 max-md:size-11 max-md:shrink-0 max-md:justify-center max-md:p-0 md:w-[calc(100%-1.5rem)]"
      >
        <Search aria-hidden="true" className="size-4 shrink-0" />
        <span className="flex-1 text-start max-md:hidden">{t("open")}</span>
        <kbd dir="ltr" className="rounded-md border border-border px-1.5 py-0.5 text-xs font-medium max-md:hidden">
          {apple ? t("shortcutMac") : t("shortcutOther")}
        </kbd>
      </Button>
      {open && <Palette tenantId={tenantId} pages={pages} actions={actions} onClose={() => setOpen(false)} />}
    </>
  );
}

function Palette({ tenantId, pages, actions, onClose }: { tenantId: string; pages: PalettePage[]; actions: QuickAction[]; onClose: () => void }) {
  const t = useTranslations("commandPalette");
  const router = useRouter();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [recents] = useState(() => readRecents(tenantId));
  const [remote, setRemote] = useState<{ query: string; hits: PaletteHit[] | null } | null>(null);

  const typed = query.trim();
  const searchable = typed.length >= MIN_SEARCH_LENGTH;

  useEffect(() => {
    if (typed.length < MIN_SEARCH_LENGTH) return;
    let current = true;
    const timer = window.setTimeout(async () => {
      const hits = await searchEverything(typed).catch(() => null);
      if (current) setRemote({ query: typed, hits });
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [typed]);

  const answer = searchable && remote?.query === typed ? remote : null;
  const failed = answer !== null && answer.hits === null;
  const searching = searchable && answer === null;

  const rows = useMemo(() => {
    const actionRows: Row[] = actions.map((action) => ({ id: `a-${action.id}`, section: "actions", label: t(`actions.${action.id}` as "actions.newClient"), href: action.href, icon: Plus }));
    if (!typed) {
      const recentRows: Row[] = recents.map((hit) => ({ id: `r-${hit.kind}-${hit.id}`, section: "recent", label: hit.title, meta: hit.meta, href: hit.href, icon: Clock, hit }));
      return [...recentRows, ...actionRows];
    }
    const found: Row[] = [...(answer?.hits ?? [])]
      .sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind))
      .map((hit) => ({ id: `h-${hit.kind}-${hit.id}`, section: hit.kind, label: hit.title, meta: hit.meta, href: hit.href, icon: KIND_ICONS[hit.kind], hit }));
    const pageRows: Row[] = pages
      .filter((page) => matches(page.label, typed))
      .slice(0, PAGES_SHOWN)
      .map((page) => ({ id: `p-${page.href}`, section: "pages", label: page.label, href: page.href, icon: CornerDownRight }));
    return [...actionRows.filter((row) => matches(row.label, typed)), ...found, ...pageRows];
  }, [actions, answer, pages, recents, t, typed]);

  const current = rows.length ? Math.min(active, rows.length - 1) : -1;
  const optionId = (index: number) => `${listId}-${index}`;

  useEffect(() => {
    if (current >= 0) document.getElementById(`${listId}-${current}`)?.scrollIntoView({ block: "nearest" });
  }, [current, listId]);

  const choose = (row: Row) => {
    if (row.hit) rememberRecent(tenantId, row.hit);
    onClose();
    router.push(row.href);
  };

  const sections: { section: Section; rows: { row: Row; index: number }[] }[] = [];
  rows.forEach((row, index) => {
    const last = sections.at(-1);
    if (last?.section === row.section) last.rows.push({ row, index });
    else sections.push({ section: row.section, rows: [{ row, index }] });
  });

  const status = failed ? t("error") : searching ? t("searching") : typed && !rows.length ? t("noResults", { query: typed }) : typed ? t("results", { count: rows.length }) : "";

  return (
    <Modal onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-3">
        <label className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2.5 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary">
          <Search aria-hidden="true" className="size-4 shrink-0 text-muted" />
          <span className="sr-only">{t("label")}</span>
          <input
            data-autofocus
            type="text"
            inputMode="search"
            enterKeyHint="search"
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={current >= 0 ? optionId(current) : undefined}
            autoComplete="off"
            spellCheck={false}
            value={query}
            placeholder={t("placeholder")}
            maxLength={100}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing || !rows.length) return;
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const step = event.key === "ArrowDown" ? 1 : -1;
                setActive((value) => (Math.max(value, 0) + step + rows.length) % rows.length);
              } else if (event.key === "Enter" && current >= 0) {
                event.preventDefault();
                choose(rows[current]);
              }
            }}
            className="min-w-0 flex-1 bg-transparent text-base focus-visible:outline-none! placeholder:text-muted"
          />
        </label>

        <p role="status" aria-live="polite" className={status ? "px-1 text-sm text-muted" : "sr-only"}>
          {status}
        </p>
        {!typed && !rows.length && <p className="px-1 text-sm text-muted">{t("hint")}</p>}
        {typed && !searchable && <p className="px-1 text-sm text-muted">{t("hint")}</p>}

        <div id={listId} role="listbox" aria-label={t("title")} className="flex flex-col gap-3">
          {sections.map(({ section, rows: group }) => (
            <div key={section} role="group" aria-labelledby={`${listId}-${section}`} className="flex flex-col">
              <h3 id={`${listId}-${section}`} className="px-2.5 pb-1 text-xs font-semibold text-muted">
                {t(`groups.${section}` as "groups.client")}
              </h3>
              {group.map(({ row, index }) => (
                <div
                  key={row.id}
                  id={optionId(index)}
                  role="option"
                  tabIndex={-1}
                  aria-selected={index === current}
                  onMouseMove={() => index !== current && setActive(index)}
                  onClick={() => choose(row)}
                  onKeyDown={(event) => event.key === "Enter" && choose(row)}
                  className="flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-sm aria-selected:bg-foreground/8"
                >
                  <row.icon aria-hidden="true" className="size-4 shrink-0 text-muted" />
                  <span dir="auto" className="min-w-0 truncate font-medium">
                    {row.label}
                  </span>
                  {row.meta ? (
                    <span dir="auto" className="ms-auto min-w-0 truncate text-xs text-muted">
                      {row.meta}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
