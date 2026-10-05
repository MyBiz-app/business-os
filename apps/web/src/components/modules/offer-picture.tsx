"use client";

import { useTranslations } from "next-intl";

/** Pictures of the CRM board and a WhatsApp reminder, for the sign-up journey and the
 * previews of modules a business doesn't have yet. */
export function OfferPicture({ offer }: { offer: "client_app" | "ai" | "crm" | "whatsapp" }) {
  const t = useTranslations("start.offers");
  if (offer === "crm") {
    const columns = t.raw("crm.columns") as string[];
    const cards = t.raw("crm.cards") as string[];
    return (
      <div className="card grid grid-cols-4 gap-2 p-4 shadow-xl">
        {columns.map((column, index) => (
          <div key={column} className="flex flex-col gap-2 rounded-xl bg-foreground/5 p-2">
            <p className="truncate text-xs font-bold">{column}</p>
            {cards.slice(index % 2, (index % 2) + (index === 3 ? 1 : 2)).map((card) => (
              <p key={card} className="rounded-lg bg-surface p-2 text-[11px] font-medium shadow-sm">
                {card}
              </p>
            ))}
          </div>
        ))}
      </div>
    );
  }
  if (offer === "whatsapp") {
    return (
      <div className="card flex flex-col gap-3 bg-emerald-50 p-5 shadow-xl dark:bg-emerald-950/40">
        <p className="max-w-[85%] self-start rounded-2xl rounded-ss-md bg-surface px-4 py-2.5 text-sm shadow-sm">{t("whatsapp.message")}</p>
        <p className="max-w-[85%] self-end rounded-2xl rounded-ee-md bg-emerald-200 px-4 py-2.5 text-sm text-emerald-950 shadow-sm">
          {t("whatsapp.reply")}
        </p>
      </div>
    );
  }
  return null;
}
