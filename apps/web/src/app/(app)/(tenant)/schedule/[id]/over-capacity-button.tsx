"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";

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
      <Button
        variant="secondary"
        aria-label={`${t("addOverCapacity")} - ${name}`}
        className="text-xs"
        onClick={() => setOpen(true)}
      >
        {t("addOverCapacity")}
      </Button>
      {open && (
        <Modal
          size="sm"
          title={t("overCapacityTitle")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <form action={waitlistAction}>
                <Button variant="secondary" type="submit">
                  {t("keepOnWaitlist")}
                </Button>
              </form>
              <form action={overAction}>
                <Button variant="primary" type="submit">
                  {t("addOverCapacity")}
                </Button>
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
