"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { addRoom, updateRoom } from "./actions";

type Room = components["schemas"]["Room"];

const INPUT = "control px-3 py-2";

function RoomRow({ room, readOnly }: { room: Room; readOnly: boolean }) {
  const t = useTranslations();
  const [state, action] = useActionState(updateRoom.bind(null, room.id, room.location_id), {});
  return (
    <li>
      <form action={action} className="flex flex-col gap-2">
        <FormFeedback state={state} />
        <fieldset disabled={readOnly} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
            {t("locations.roomName")}
            <input name="name" required maxLength={120} defaultValue={room.name} className={INPUT} />
          </label>
          <label className="flex w-28 flex-col gap-1 text-sm font-medium">
            {t("locations.roomCapacity")}
            <input name="capacity" type="number" min={1} max={1000} defaultValue={room.capacity ?? ""} className={INPUT} />
          </label>
          <label className="flex items-center gap-2 pb-2.5 text-sm">
            <input name="active" type="checkbox" defaultChecked={room.active} className="size-4 accent-primary" />
            {t("common.active")}
          </label>
          <label className="flex items-center gap-2 pb-2.5 text-sm">
            <input name="bookable" type="checkbox" defaultChecked={room.bookable} className="size-4 accent-primary" />
            {t("locations.bookable")}
          </label>
          {!readOnly && <SubmitButton>{t("common.save")}</SubmitButton>}
        </fieldset>
      </form>
      {room.bookable && (
        <Link
          href={`/locations/${room.location_id}/rooms/${room.id}`}
          className="mt-1 inline-block text-sm text-primary underline-offset-4 hover:underline"
        >
          {t("locations.openingHours", { name: room.name })}
        </Link>
      )}
    </li>
  );
}

function AddRoom({ locationId }: { locationId: string }) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(addRoom.bind(null, locationId), {});
  return (
    <form action={action} className="flex flex-col gap-2 border-t border-border pt-4">
      <FormFeedback state={state} />
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
          {t("locations.roomName")}
          <input name="name" required maxLength={120} className={INPUT} />
        </label>
        <label className="flex w-28 flex-col gap-1 text-sm font-medium">
          {t("locations.roomCapacity")}
          <input name="capacity" type="number" min={1} max={1000} className={INPUT} />
        </label>
        <label className="flex items-center gap-2 pb-2.5 text-sm">
          <input name="bookable" type="checkbox" className="size-4 accent-primary" />
          {t("locations.bookable")}
        </label>
        <SubmitButton>{t("locations.addRoom")}</SubmitButton>
      </div>
    </form>
  );
}

export function Rooms({ locationId, rooms, readOnly }: { locationId: string; rooms: Room[]; readOnly: boolean }) {
  const t = useTranslations("locations");
  return (
    <div className="flex flex-col gap-4">
      {rooms.length === 0 ? (
        <p className="text-sm text-muted">{t("noRooms")}</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {rooms.map((room) => (
            // Keyed by name and capacity so a save remounts the row with stored values.
            <RoomRow key={`${room.id}-${room.name}-${room.capacity}-${room.active}-${room.bookable}`} room={room} readOnly={readOnly} />
          ))}
        </ul>
      )}
      {!readOnly && <AddRoom key={rooms.length} locationId={locationId} />}
    </div>
  );
}
