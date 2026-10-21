"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { markAnnouncement } from "@/app/(app)/announcements-actions";
import { useTourOpen } from "@/components/tour/tour-state";
import { Modal } from "@/components/ui/modal";
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
 * close it (then it never comes back). It uses the product's window, and waits while a guided
 * tour is open instead of opening over it. */
export function AnnouncementsPopup({ items }: { items: PopupItem[] }) {
  const t = useTranslations("app.announcements");
  const [queue, setQueue] = useState(items);
  const touring = useTourOpen();
  const current = queue[0];
  const currentId = current?.id;
  const showing = Boolean(currentId) && !touring;

  useEffect(() => {
    if (showing && currentId) void markAnnouncement(currentId, "viewed");
  }, [showing, currentId]);

  const dismiss = () => {
    if (!current) return;
    void markAnnouncement(current.id, "dismissed");
    setQueue((q) => q.slice(1));
  };

  if (!current) return null;
  return (
    <Modal open={showing} onClose={dismiss} size="sm" title={current.subject} description={t("label", { brand: BRAND.name })}>
      <div className="flex flex-col gap-4">
        {current.imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element -- an address the MyBiz team typed in
          <img src={current.imageUrl} alt="" className="max-h-48 w-full rounded-xl object-cover" />
        )}
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
    </Modal>
  );
}
