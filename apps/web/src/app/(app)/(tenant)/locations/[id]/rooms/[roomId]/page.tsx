import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { HoursForm } from "@/components/form/hours-form";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { toBlocks, weekStartFor } from "@/lib/hours";
import { getTenantFor } from "@/lib/tenant";

import { saveRoomHours } from "../../../actions";

/** A bookable room's (a court's) weekly opening hours: when it can be reserved. */
export default async function RoomHoursPage({ params }: PageProps<"/locations/[id]/rooms/[roomId]">) {
  const { id, roomId } = await params;
  const t = await getTranslations();
  const { api, scope, tenant } = await getTenantFor("catalog.write");
  const { data: location } = await api.GET("/locations/{location_id}", { params: { ...scope, path: { location_id: id } } });
  const room = location?.rooms.find((r) => r.id === roomId);
  if (!location || !room) notFound();
  const hours = unwrap(await api.GET("/rooms/{room_id}/hours", { params: { ...scope, path: { room_id: roomId } } }));

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href={`/locations/${id}`} className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("locations.openingHours", { name: isolate(room.name) })}</h1>
        <p className="text-muted">{t("resources.hoursHint", { branch: isolate(location.name) })}</p>
      </div>
      {!room.bookable && <p role="status" className="card p-4 text-sm">{t("resources.notBookable")}</p>}
      <section className="card p-6">
        <HoursForm save={saveRoomHours.bind(null, roomId, id)} weekStartsOn={weekStartFor(tenant.locale)} initial={toBlocks(hours.blocks)} />
      </section>
    </main>
  );
}
