"use client";

import { categories, isOpen } from "@business-os/verticals";
import { useTranslations } from "next-intl";

import { VerticalIcon } from "@/components/vertical-icon";
import { industryTexts } from "@/lib/verticals";

/** The first calculator question: what kind of business. It only marks the add-ons that suit the
 * business as "recommended"; it never changes a price. */
export function CalcIndustry({ value, onChange }: { value: string | null; onChange: (vertical: string | null) => void }) {
  const t = useTranslations("marketing.pricing.calc");
  const { text } = industryTexts(useTranslations());
  const open = categories().filter((category) => isOpen(category.key));
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="font-bold">
        <span aria-hidden="true" className="me-2 text-primary-ink">①</span>
        {t("industry")}
      </legend>
      <div className="flex flex-wrap gap-2">
        {open.map((category) => {
          const pressed = value === category.key;
          return (
            <button
              key={category.key}
              type="button"
              aria-pressed={pressed}
              onClick={() => onChange(pressed ? null : category.key)}
              className={`btn-plain flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-semibold transition-colors ${
                pressed ? "border-primary bg-primary/10 text-primary-ink ring-1 ring-primary" : "border-border hover:bg-foreground/5"
              }`}
            >
              <span aria-hidden="true" className={`flex size-6 items-center justify-center rounded-full bg-gradient-to-br text-white ${category.color}`}>
                <VerticalIcon icon={category.icon} className="size-3.5" />
              </span>
              {text(category.key, "name")}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
