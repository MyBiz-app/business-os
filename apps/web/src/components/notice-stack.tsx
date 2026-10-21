"use client";

import { Bell, ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

/** Groups the top notices (legal documents, home address). On a phone two stacked banners push the
 * content down, so with more than one notice they fold into a single thin row that opens on tap;
 * on larger screens (and with a single notice) they show as usual. */
export function NoticeStack({ count, children }: { count: number; children: ReactNode }) {
  const t = useTranslations("noticeStack");
  const [open, setOpen] = useState(false);
  if (count === 0) return null;
  if (count === 1) return <>{children}</>;
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="btn-plain flex min-h-11 w-full items-center justify-center gap-2 border-b border-border bg-primary/10 px-4 text-sm font-medium md:hidden"
      >
        <Bell aria-hidden="true" className="size-4" />
        <span>{t("summary", { count })}</span>
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
        <span className="sr-only">{t("toggle")}</span>
      </button>
      <div className={open ? "block" : "hidden md:block"}>{children}</div>
    </div>
  );
}
