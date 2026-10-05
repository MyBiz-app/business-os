"use client";

import { Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

type Props = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string; hint?: string };

/** A file input in the app's language and style (the browser's own button speaks the browser's
 * language). The real input stays in place for keyboards, screen readers and forms. */
export function FileField({ label, hint, onChange, ...inputProps }: Props) {
  const t = useTranslations("common");
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const [name, setName] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium" id={`${id}-label`}>
        {label}
      </span>
      <label
        htmlFor={id}
        className="control flex cursor-pointer items-center gap-3 px-3 py-2 has-[:focus-visible]:border-primary has-[:focus-visible]:shadow-[0_0_0_4px_color-mix(in_oklab,var(--primary)_18%,transparent)]"
      >
        <span className="btn-secondary shrink-0 px-3 py-1.5 text-sm">
          <Upload aria-hidden="true" className="size-4" />
          {t("chooseFile")}
        </span>
        <span className={`truncate text-sm ${name ? "" : "text-muted"}`}>{name ?? t("noFile")}</span>
        <input
          id={id}
          type="file"
          aria-labelledby={`${id}-label`}
          aria-describedby={hintId}
          className="sr-only"
          onChange={(event) => {
            setName(event.target.files?.[0]?.name ?? null);
            onChange?.(event);
          }}
          {...inputProps}
        />
      </label>
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
