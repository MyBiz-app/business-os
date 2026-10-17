import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";

import { AppointmentBody } from "../../../schedule/appointment/appointment-body";

export default async function NewAppointmentModal({ searchParams }: PageProps<"/schedule/appointment">) {
  const t = await getTranslations("appointments");
  const query = await searchParams;
  return (
    <RouteModal title={t("title")}>
      <AppointmentBody query={query} />
    </RouteModal>
  );
}
