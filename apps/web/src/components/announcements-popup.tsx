"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { markAnnouncement } from "@/app/(app)/announcements-actions";
import { BRAND } from "@business-os/i18n/brand";

export type PopupItem = {
  id: string;
  subject: string;
  body: string;
  ctaLabel: string;
  ctaUrl: string;
  imageUrl: string;
};

/** The messages MyBiz sent as a pop-up: one at a time, on the person's next visit, until they
 * close it (then it never comes back). */
export function AnnouncementsPopup({ items }: { items: PopupItem[] }) {
  const t = useTranslations("app.announcements");
  const [queue, setQueue] = useState(items);
  const close = useRef<HTMLButtonElement>(null);
  const current = queue[0];
  const currentId = current?.id;

  useEffect(() => {
    if (!currentId) return;
    void markAnnouncement(currentId, "viewed");
    close.current?.focus();
  }, [currentId]);

  const dismiss = () => {
    if (!current) return;
    void markAnnouncement(current.id, "dismissed");
    setQueue((q) => q.slice(1));
  };

  if (!current) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onKeyDown={(e) => e.key === "Escape" && dismiss()}>
      <div role="dialog" aria-modal="true" aria-label={t("label", { brand: BRAND.name })} className="relative flex max-h-[90dvh] w-full max-w-md flex-col gap-4 overflow-y-auto rounded-2xl bg-surface p-6 shadow-xl">
        <button ref={close} type="button" onClick={dismiss} aria-label={t("close")} className="btn-plain absolute end-3 top-3 rounded-full p-1.5 hover:bg-foreground/10">
          <X aria-hidden="true" className="size-5" />
        </button>
        {current.imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element -- an address the MyBiz team typed in
          <img src={current.imageUrl} alt="" className="max-h-48 w-full rounded-xl object-cover" />
        )}
        <h2 className="pe-8 text-lg font-semibold" dir="auto">
          {current.subject}
        </h2>
        <p className="whitespace-pre-line text-sm" dir="auto">
          {current.body}
        </p>
        {current.ctaUrl && (
          <a
            href={current.ctaUrl}
            onClick={() => {
              void markAnnouncement(current.id, "clicked");
              dismiss();
            }}
            className="btn-primary self-start px-4 py-2.5"
          >
            {current.ctaLabel || t("close")}
          </a>
        )}
      </div>
    </div>
  );
}
