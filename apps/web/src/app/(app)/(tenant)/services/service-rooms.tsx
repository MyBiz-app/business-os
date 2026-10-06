"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

type Room = { id: string; name: string; branch: string };

/** The courts / rooms that serve a resource service: a checklist of the bookable rooms. */
export function ServiceRooms({
  action,
  rooms,
  selected,
  readOnly,
}: {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  rooms: Room[];
  selected: string[];
  readOnly: boolean;
}) {
  const t = useTranslations("resources");
  const [state, formAction] = useActionState(action, {});
  if (rooms.length === 0) {
    return (
      <p className="text-sm text-muted">
        {t("noBookableRooms")}{" "}
        <Link href="/locations" className="text-primary underline-offset-4 hover:underline">
          {t("toLocations")}
        </Link>
      </p>
    );
  }
  return (
    <form action={formAction} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <fieldset disabled={readOnly} className="flex flex-col gap-2">
        <legend className="sr-only">{t("rooms")}</legend>
        {rooms.map((room) => (
          <label key={room.id} className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="room_id" value={room.id} defaultChecked={selected.includes(room.id)} className="size-4 accent-primary" />
            <span className="font-medium">{room.name}</span>
            <span className="text-muted">· {room.branch}</span>
          </label>
        ))}
      </fieldset>
      {!readOnly && (
        <div>
          <SubmitButton>{t("saveRooms")}</SubmitButton>
        </div>
      )}
    </form>
  );
}
