"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { locales } from "@/i18n/config";
import { setLocale } from "@/i18n/actions";

export function LocaleSwitcher() {
  const t = useTranslations();
  const current = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">{t("settings.language")}</span>
      <select
        className="rounded-md border border-border bg-surface px-2 py-1"
        value={current}
        disabled={pending}
        onChange={(event) => {
          const next = event.target.value;
          startTransition(async () => {
            await setLocale(next);
            router.refresh();
          });
        }}
      >
        {locales.map((locale) => (
          <option key={locale} value={locale}>
            {t(`locales.${locale}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
