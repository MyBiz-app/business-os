import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { HoursForm } from "@/components/form/hours-form";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { toBlocks, weekStartFor } from "@/lib/hours";
import { getTenantFor } from "@/lib/tenant";

import { saveRoomHours } from "../../../actions";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

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
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href={`/locations/${id}`} label={t("common.back")} />
      <PageHeader title={t("locations.openingHours", { name: isolate(room.name) })} description={t("resources.hoursHint", { branch: isolate(location.name) })} />
      {!room.bookable && <p role="status" className="card p-4 text-sm">{t("resources.notBookable")}</p>}
      <section className="card p-6">
        <HoursForm save={saveRoomHours.bind(null, roomId, id)} weekStartsOn={weekStartFor(tenant.locale)} initial={toBlocks(hours.blocks)} />
      </section>
    </Container>
  );
}
