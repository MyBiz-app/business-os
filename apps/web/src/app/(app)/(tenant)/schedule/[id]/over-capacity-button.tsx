"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Modal } from "@/components/ui/modal";

/** "Add over capacity" for a full class: asks first, then books the client beyond the capacity.
 * `overAction` books over capacity, `waitlistAction` queues the client as usual. */
export function OverCapacityButton({
  name,
  booked,
  capacity,
  overAction,
  waitlistAction,
}: {
  name: string;
  booked: number;
  capacity: number;
  overAction: () => Promise<void>;
  waitlistAction: () => Promise<void>;
}) {
  const t = useTranslations("bookings");
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-label={`${t("addOverCapacity")} - ${name}`}
        className="btn-secondary px-3 py-1 text-xs"
        onClick={() => setOpen(true)}
      >
        {t("addOverCapacity")}
      </button>
      {open && (
        <Modal
          size="sm"
          title={t("overCapacityTitle")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <form action={waitlistAction}>
                <button type="submit" className="btn-secondary px-4 py-2">
                  {t("keepOnWaitlist")}
                </button>
              </form>
              <form action={overAction}>
                <button type="submit" className="btn-primary px-4 py-2">
                  {t("addOverCapacity")}
                </button>
              </form>
            </>
          }
        >
          <p dir="auto" className="rounded-lg border border-warning/50 bg-warning/10 px-3 py-2 text-sm">
            {t("overCapacityBody", { booked, capacity, name })}
          </p>
        </Modal>
      )}
    </>
  );
}
