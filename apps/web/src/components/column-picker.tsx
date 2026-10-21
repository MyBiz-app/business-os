"use client";

import { Columns3 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";

/** The query parameter that lists the hidden columns, so a view (a bookmark, a saved view) keeps them. */
export const HIDDEN_COLUMNS_PARAM = "hide";

export function hiddenColumns(value: string | string[] | undefined, allowed: string[]) {
  const raw = Array.isArray(value) ? value.join(",") : (value ?? "");
  return raw.split(",").filter((key) => allowed.includes(key));
}

/** Chooses which columns of a list show. The choice goes into the URL (`hide=phone,email`), where
 * the server page reads it, so it travels with the filters and with saved views. */
export function ColumnPicker({ columns, hidden }: { columns: { key: string; label: string }[]; hidden: string[] }) {
  const t = useTranslations("tableViews");
  const router = useRouter();
  const params = useSearchParams();

  const apply = (next: string[]) => {
    const query = new URLSearchParams(params.toString());
    if (next.length) query.set(HIDDEN_COLUMNS_PARAM, next.join(","));
    else query.delete(HIDDEN_COLUMNS_PARAM);
    router.replace(`?${query}`, { scroll: false });
  };
  const toggle = (key: string) => apply(hidden.includes(key) ? hidden.filter((k) => k !== key) : [...hidden, key]);

  return (
    <Popover
      label={t("columnsLabel")}
      className="w-56 p-1.5"
      trigger={(props) => (
        <Button {...props} variant="secondary">
          <Columns3 aria-hidden="true" className="size-4" />
          {t("columns")}
        </Button>
      )}
    >
      <fieldset className="flex flex-col gap-0.5">
        <legend className="sr-only">{t("columnsLabel")}</legend>
        {columns.map(({ key, label }) => (
          <label key={key} className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-sm hover:bg-subtle">
            <input type="checkbox" checked={!hidden.includes(key)} onChange={() => toggle(key)} className="size-4 accent-primary" />
            {label}
          </label>
        ))}
        {hidden.length > 0 && (
          <Button variant="quiet" onClick={() => apply([])} className="mt-1">
            {t("reset")}
          </Button>
        )}
      </fieldset>
    </Popover>
  );
}
