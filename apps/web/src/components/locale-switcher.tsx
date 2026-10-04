"use client";

import { Languages } from "lucide-react";
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
    <label className="relative flex items-center text-sm">
      <span className="sr-only">{t("settings.language")}</span>
      <Languages aria-hidden="true" className="pointer-events-none absolute start-2.5 size-4 text-muted" />
      <select
        className="control h-9 ps-8 pe-2"
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
