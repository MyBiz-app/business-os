import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { AppointmentBody } from "./appointment-body";

/** Book a personal appointment: service, staff and day pick the free times; then the client. */
export default async function NewAppointmentPage({ searchParams }: PageProps<"/schedule/appointment">) {
  const t = await getTranslations();
  const query = await searchParams;
  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/schedule" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <PageHeader title={t("appointments.title")} />
      <AppointmentBody query={query} />
    </Container>
  );
}
