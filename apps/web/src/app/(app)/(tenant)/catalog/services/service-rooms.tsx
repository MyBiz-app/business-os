"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

type Room = { id: string; name: string; branch: string };

/** The courts / rooms that serve a resource service: a checklist of the bookable rooms. It sits
 * inside the service form and is saved with it. */
export function ServiceRooms({ rooms, selected, readOnly }: { rooms: Room[]; selected: string[]; readOnly: boolean }) {
  const t = useTranslations("resources");
  return (
    <section aria-labelledby="rooms-heading" className="flex flex-col gap-3 border-t border-border pt-4">
      <div className="flex flex-col gap-1">
        <h3 id="rooms-heading" className="font-semibold">{t("rooms")}</h3>
        <p className="text-sm text-muted">{t("roomsHint")}</p>
      </div>
      {rooms.length === 0 ? (
        <p className="text-sm text-muted">
          {t("noBookableRooms")}{" "}
          <Link href="/locations" className="text-primary-ink underline-offset-4 hover:underline">
            {t("toLocations")}
          </Link>
        </p>
      ) : (
        <fieldset disabled={readOnly} className="flex flex-col gap-2">
          <legend className="sr-only">{t("rooms")}</legend>
          <input type="hidden" name="rooms_listed" value="1" />
          {rooms.map((room) => (
            <label key={room.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="room_id" value={room.id} defaultChecked={selected.includes(room.id)} className="size-4 accent-primary" />
              <span className="font-medium">{room.name}</span>
              <span className="text-muted">· {room.branch}</span>
            </label>
          ))}
        </fieldset>
      )}
    </section>
  );
}
