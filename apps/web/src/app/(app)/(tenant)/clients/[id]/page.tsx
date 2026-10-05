import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/avatar";
import { ReviewsSummary } from "@/components/reviews-summary";
import { unwrap } from "@/lib/api";
import { formatTime } from "@/lib/dates";
import { canWriteClients } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { updateClient } from "../actions";
import { ClientForm } from "../client-form";
import { StatusBadge } from "../status-badge";
import { HealthSection } from "./health-section";
import { PlansSection } from "./plans-section";
import { PrivacySection } from "./privacy-section";
import { MessagesSection } from "../../messages/messages-section";
import { NotesSection, ProfileSection } from "./profile-section";

/** Bookings arrive newest first; upcoming ones are shown soonest first. */
function splitByNow<T extends { starts_at: string }>(bookings: T[]) {
  const now = Date.now();
  return {
    upcoming: bookings.filter((b) => Date.parse(b.starts_at) >= now).reverse(),
    past: bookings.filter((b) => Date.parse(b.starts_at) < now),
  };
}

export default async function ClientPage({ params }: PageProps<"/clients/[id]">) {
  const { id } = await params;
  const t = await getTranslations("clients");
  const tBookings = await getTranslations("bookings");
  const tPrivacy = await getTranslations("privacy");
  const locale = await getLocale();
  const context = await getTenantFor("clients.read");
  const { tenant, api, scope } = context;

  const { data: client } = await api.GET("/clients/{client_id}", {
    params: { ...scope, path: { client_id: id } },
  });
  if (!client) notFound();

  const joined = new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
    new Date(client.created_at),
  );
  const erased = client.erased_at !== null;
  const writable = canWriteClients(tenant) && !erased;
  const bookings = unwrap(
    await api.GET("/clients/{client_id}/bookings", { params: { ...scope, path: { client_id: id } } }),
  );
  const { upcoming, past } = splitByNow(bookings);
  const reviews = unwrap(await api.GET("/reviews", { params: { ...scope, query: { client_id: id } } }));
  const tReviews = await getTranslations("reviews");
  const dateFormat = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: tenant.time_zone,
  });
  const bookingList = (items: typeof bookings) => (
    <ul className="flex flex-col divide-y divide-border">
      {items.map((booking) => (
        <li key={booking.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
          <Link href={`/schedule/${booking.session_id}`} className="flex flex-col underline-offset-4 hover:underline">
            <span className="font-medium">{booking.service_name}</span>
            <span className="text-sm text-muted">
              {dateFormat.format(new Date(booking.starts_at))} ·{" "}
              <span dir="ltr">{formatTime(booking.starts_at, locale, tenant.time_zone)}</span>
            </span>
          </Link>
          <span className="text-sm text-muted">
            {booking.session_status === "cancelled"
              ? tBookings("sessionCancelled")
              : tBookings(`statuses.${booking.status}`)}
            {booking.late_cancel && ` · ${tBookings("lateCancel")}`}
          </span>
        </li>
      ))}
    </ul>
  );

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/clients" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-4">
          <Avatar id={client.id} name={[client.first_name, client.last_name].filter(Boolean).join(" ")} size="lg" />
          <h1 className="text-3xl font-bold">{[client.first_name, client.last_name].filter(Boolean).join(" ")}</h1>
        </div>
        <StatusBadge status={client.status} />
      </div>
      <p className="text-sm text-muted">{t("joined", { date: joined })}</p>
      {client.erased_at && (
        <p role="status" className="rounded-lg border border-border bg-surface px-4 py-3 text-sm">
          {tPrivacy("erasedOn", {
            date: new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
              new Date(client.erased_at),
            ),
          })}
        </p>
      )}

      <section aria-labelledby="details-heading" className="card p-6">
        <h2 id="details-heading" className="mb-4 text-lg font-semibold">
          {t("details")}
        </h2>
        <ClientForm
          action={updateClient.bind(null, client.id)}
          client={client}
          submitLabel={t("save")}
          readOnly={!writable}
          branches={await getBranches()}
        />
      </section>

      <ProfileSection clientId={client.id} values={client.custom_fields} context={context} locked={erased} />

      {!erased && tenant.requires_health_declaration && <HealthSection clientId={client.id} context={context} />}

      <PlansSection clientId={client.id} context={context} locked={erased} />

      <section aria-labelledby="bookings-heading" className="flex flex-col gap-4 card p-6">
        <h2 id="bookings-heading" className="text-lg font-semibold">
          {tBookings("title")}
        </h2>
        {bookings.length === 0 && <p className="text-sm text-muted">{tBookings("noneYet")}</p>}
        {upcoming.length > 0 && (
          <div className="flex flex-col gap-1">
            <h3 className="font-semibold">{tBookings("upcoming")}</h3>
            {bookingList(upcoming)}
          </div>
        )}
        {past.length > 0 && (
          <div className="flex flex-col gap-1">
            <h3 className="font-semibold">{tBookings("history")}</h3>
            {bookingList(past)}
          </div>
        )}
      </section>

      {reviews.count > 0 && (
        <ReviewsSummary
          summary={reviews}
          locale={locale}
          timeZone={tenant.time_zone}
          title={tReviews("clientTitle")}
          withClients={false}
          withGroups={false}
        />
      )}

      <NotesSection clientId={client.id} bookings={bookings} context={context} locked={erased} />

      <MessagesSection
        target={{ client_id: client.id }}
        phone={client.phone}
        path={`/clients/${client.id}`}
        context={context}
        locked={erased}
      />

      {!erased && tenant.permissions.includes("clients.privacy") && (
        <PrivacySection
          clientId={client.id}
          name={[client.first_name, client.last_name].filter(Boolean).join(" ")}
        />
      )}
    </main>
  );
}
