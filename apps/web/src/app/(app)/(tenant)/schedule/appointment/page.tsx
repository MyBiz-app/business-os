import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { unwrap } from "@/lib/api";
import { formatTime, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

import { BookingForm } from "./booking-form";

/** Book a personal appointment: service, staff and day pick the free times; then the client. */
export default async function NewAppointmentPage({ searchParams }: PageProps<"/schedule/appointment">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("bookings.manage");
  const query = await searchParams;
  const param = (name: string) => (typeof query[name] === "string" ? (query[name] as string) : "");
  const today = todayIn(tenant.time_zone);

  const [services, staff] = await Promise.all([
    api.GET("/services", { params: { ...scope, query: { active: true } } }).then(unwrap),
    api.GET("/appointments/staff", { params: scope }).then(unwrap),
  ]);
  const appointmentServices = services.filter((service) => service.booking_mode === "appointment");
  const serviceId = param("service") || appointmentServices[0]?.id || "";
  const staffId = param("staff");
  const day = param("date") || today;
  const search = param("q");

  const [slots, clients] = await Promise.all([
    serviceId && staff.length > 0
      ? api
          .GET("/appointments/slots", {
            params: { ...scope, query: { service_id: serviceId, date: day, ...(staffId ? { staff_user_id: staffId } : {}) } },
          })
          .then(unwrap)
      : Promise.resolve([]),
    api.GET("/clients", { params: { ...scope, query: { limit: 20, status: "active", ...(search ? { search } : {}) } } }).then(unwrap),
  ]);

  // Industries that keep pets / children book one of them (the owner pays).
  const dependents = unwrap(await api.GET("/dependents/settings", { params: scope }));
  const choices = (
    await Promise.all(
      clients.items.map(async (client) => {
        const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
        const detail = client.phone ?? client.email ?? "";
        if (!dependents.kind) return [{ id: client.id, name, detail }];
        const theirs = unwrap(
          await api.GET("/clients/{client_id}/dependents", { params: { ...scope, path: { client_id: client.id } } }),
        ).filter((d) => d.active);
        return [
          ...theirs.map((d) => ({ id: `${client.id}|${d.id}`, name: `${d.name} · ${name}`, detail })),
          ...(dependents.required ? [] : [{ id: client.id, name, detail }]),
        ];
      }),
    )
  ).flat();
  const terms = (key: string) => t(`terms.${termsOf(tenant.vertical)}.${key}` as "terms.fitness.clients");

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/schedule" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <h1 className="text-3xl font-bold">{t("appointments.title")}</h1>

      {appointmentServices.length === 0 ? (
        <p className="card p-6 text-muted">{t("appointments.noServices")}</p>
      ) : staff.length === 0 ? (
        <p className="card p-6 text-muted">{t("appointments.noStaff")}</p>
      ) : (
        <>
          {/* Changing these reloads the free times (a plain GET form, works without JavaScript). */}
          <form method="get" className="card grid gap-4 p-6 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("appointments.service")}
              <select name="service" defaultValue={serviceId} className="control px-3 py-2 font-normal">
                {appointmentServices.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name} · {t("services.minutes", { count: service.duration_minutes })}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("appointments.staff")}
              <select name="staff" defaultValue={staffId} className="control px-3 py-2 font-normal">
                <option value="">{t("appointments.anyStaff")}</option>
                {staff.map((member) => (
                  <option key={member.user_id} value={member.user_id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("appointments.date")}
              <input type="date" name="date" min={today} defaultValue={day} className="control px-3 py-2 font-normal" />
            </label>
            {search && <input type="hidden" name="q" value={search} />}
            <button type="submit" className="btn-secondary px-4 py-2">
              {t("appointments.show")}
            </button>
          </form>

          <section aria-labelledby="slots-heading" className="card flex flex-col gap-5 p-6">
            <h2 id="slots-heading" className="text-lg font-semibold">
              {t("appointments.slots")}
            </h2>
            <form method="get" className="flex gap-2">
              <input type="hidden" name="service" value={serviceId} />
              <input type="hidden" name="staff" value={staffId} />
              <input type="hidden" name="date" value={day} />
              <label className="flex-1">
                <span className="sr-only">{t("appointments.searchClient")}</span>
                <input name="q" defaultValue={search} placeholder={t("appointments.searchClient")} className="control w-full px-3 py-2" />
              </label>
              <button type="submit" className="btn-secondary px-4 py-2">
                {t("appointments.search")}
              </button>
            </form>
            {slots.length === 0 ? (
              <p className="text-muted">{t("appointments.noSlots")}</p>
            ) : choices.length === 0 ? (
              <p className="text-muted">{terms("noResults")}</p>
            ) : (
              <BookingForm
                key={`${serviceId}-${staffId}-${day}-${search}`}
                serviceId={serviceId}
                slots={slots.map((slot) => ({
                  value: `${slot.staff_user_id}|${slot.starts_at}`,
                  time: formatTime(slot.starts_at, locale, tenant.time_zone),
                  staff: slot.staff_name,
                }))}
                clients={choices}
              />
            )}
          </section>
        </>
      )}
    </main>
  );
}
