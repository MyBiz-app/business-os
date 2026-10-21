"use client";

import { Bookmark, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";

import { Button, IconButton } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";

type View = { id: string; name: string; query: string };

/** Parameters that describe the position in the list, not the list itself. */
const TRANSIENT = ["page", "pages", "open"];

function currentQuery(params: URLSearchParams) {
  const next = new URLSearchParams(params);
  for (const key of TRANSIENT) next.delete(key);
  return next.toString();
}

const CHANGED = "saved-views-changed";

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGED, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function parse(raw: string): View[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is View => typeof v?.id === "string" && typeof v?.name === "string" && typeof v?.query === "string") : [];
  } catch {
    return [];
  }
}

function readRaw(storageKey: string) {
  try {
    return localStorage.getItem(storageKey) ?? "[]";
  } catch {
    return "[]";
  }
}

/** Saved views of a list: a name for a set of filters, sort and columns (the query string of the
 * page). They live in this browser, per business, so nothing about them reaches the server. */
export function SavedViews({ storageKey, basePath }: { storageKey: string; basePath: string }) {
  const t = useTranslations("tableViews");
  const router = useRouter();
  const params = useSearchParams();
  const raw = useSyncExternalStore(subscribe, () => readRaw(storageKey), () => "[]");
  const views = useMemo(() => parse(raw), [raw]);
  const [name, setName] = useState("");
  const query = currentQuery(new URLSearchParams(params.toString()));

  const persist = (next: View[]) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      // Storage is blocked (private window): nothing is kept.
    }
    window.dispatchEvent(new Event(CHANGED));
  };
  const add = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    persist([...views, { id: crypto.randomUUID(), name: trimmed, query }]);
    setName("");
  };
  const open = (view: View, close: () => void) => {
    close();
    router.push(view.query ? `${basePath}?${view.query}` : basePath, { scroll: false });
  };

  return (
    <Popover
      label={t("saved")}
      className="w-72 p-3"
      trigger={(props) => (
        <Button {...props} variant="secondary">
          <Bookmark aria-hidden="true" className="size-4" />
          {t("saved")}
        </Button>
      )}
    >
      {({ close }) => (
        <div className="flex flex-col gap-3">
          {views.length === 0 ? (
            <p className="text-sm text-muted">{t("none")}</p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {views.map((view) => (
                <li key={view.id} className="flex items-center gap-1">
                  <Button
                    variant="plain"
                    aria-current={view.query === query ? "true" : undefined}
                    onClick={() => open(view, close)}
                    className="min-h-9 flex-1 truncate rounded-lg px-2.5 text-start text-sm hover:bg-subtle aria-[current=true]:font-semibold aria-[current=true]:text-primary-ink"
                  >
                    <span dir="auto">{view.name}</span>
                  </Button>
                  <IconButton label={t("remove", { name: view.name })} onClick={() => persist(views.filter((v) => v.id !== view.id))}>
                    <X aria-hidden="true" className="size-4" />
                  </IconButton>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("name")}
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter") return;
                  event.preventDefault(); // the list's own filter form must not submit
                  add();
                }}
                maxLength={60}
                placeholder={t("namePlaceholder")}
                className="control px-3 py-2 font-normal"
              />
            </label>
            <Button variant="primary" disabled={!name.trim()} onClick={add}>
              {t("save")}
            </Button>
            <p className="text-xs text-muted">{t("devicenote")}</p>
          </div>
        </div>
      )}
    </Popover>
  );
}
