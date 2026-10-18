import { getTranslations } from "next-intl/server";

import { isolate } from "@/lib/bidi";
import { brandStyle } from "@/lib/brand";

/** A small picture of what a MyBiz website looks like for this business: its name and color, and
 * the sections that fit its field. Decorative, so it is hidden from screen readers. */
export async function SitePreview({ name, color, vertical }: { name: string; color: string | null; vertical: string }) {
  const t = await getTranslations("website.preview");
  const terms = await getTranslations(`terms.${vertical}` as "terms.fitness");
  return (
    <div aria-hidden="true" className="brand overflow-hidden rounded-2xl border border-border bg-surface shadow-sm" style={brandStyle(color)}>
      <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
        <span className="size-2.5 rounded-full bg-foreground/15" />
        <span className="size-2.5 rounded-full bg-foreground/15" />
        <span className="size-2.5 rounded-full bg-foreground/15" />
        <span className="ms-3 h-4 flex-1 rounded-full bg-foreground/8" />
      </div>
      <div className="flex flex-col gap-4 p-5">
        <div className="btn-primary flex flex-col gap-2 rounded-xl p-5">
          <span className="text-xl font-bold">{isolate(name)}</span>
          <span className="text-sm opacity-90">{t("tagline")}</span>
          <span className="mt-1 w-fit rounded-full bg-background px-3 py-1 text-xs font-semibold text-foreground">{terms("schedule")}</span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs font-medium">
          {[t("services"), terms("schedule"), t("contact")].map((label) => (
            <span key={label} className="rounded-lg border border-border px-2 py-3">{label}</span>
          ))}
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="h-2 w-3/4 rounded-full bg-foreground/10" />
          <span className="h-2 w-1/2 rounded-full bg-foreground/10" />
        </div>
      </div>
    </div>
  );
}
