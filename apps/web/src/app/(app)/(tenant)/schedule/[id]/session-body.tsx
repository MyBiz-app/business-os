import { FormNotice } from "@/components/form/form-message";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { unwrap } from "@/lib/api";
import { dayOf, formatDay, formatTime } from "@/lib/dates";
import { canManageBookings, canWriteSchedule } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { formatMoney } from "@/lib/money";

import { endSeries, recordVenuePayment, updateSession } from "../actions";
import { SessionForm } from "../session-form";
import { JobPanel } from "./job-panel";
import { Roster } from "./roster";
import { SessionStatusButton } from "./session-status-button";
import { UserText, Ltr } from "@/components/bidi";
import { PageHeader } from "@/components/layout/page-header";

type Query = Record<string, string | string[] | undefined>;

/** One class or booking: the page and the window over the schedule show the same thing. */
export async function SessionBody({ id, query, inModal = false }: { id: string; query: Query; inModal?: boolean }) {
  const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
  const t = await getTranslations("schedule");
  const tCommon = await getTranslations("common");
  const locale = await getLocale();
  const context = await getTenantFor("schedule.read");
  const { tenant, api, scope } = context;
  const { data: session } = await api.GET("/sessions/{session_id}", {
    params: { ...scope, path: { session_id: id } },
  });
  if (!session) notFound();

  const writable = canWriteSchedule(tenant);
  const options = writable
    ? unwrap(await api.GET("/sessions/options", { params: scope }))
    : { services: [{ id: session.service.id, name: session.service.name, duration_minutes: 0, capacity: 0 }], locations: [], rooms: [], instructors: [] };
  const day = dayOf(session.starts_at, tenant.time_zone);
  const minutes = Math.round((Date.parse(session.ends_at) - Date.parse(session.starts_at)) / 60000);
  const cancelled = session.status === "cancelled";
  // A reservation of a court or room: its time and room come from the reservation itself, so
  // it isn't edited like a class (cancel the booking to free the court).
  const reservation = session.booking_mode === "resource";
  const reservedBy = reservation
    ? (await api.GET("/sessions/{session_id}/bookings", { params: { ...scope, path: { session_id: id } } }).then(unwrap)).find(
        (b) => b.status !== "cancelled",
      )
    : undefined;
  const tResources = await getTranslations("resources");
  const endedParam = first(query.ended)?.split("-").map(Number);
  const ended = endedParam?.length === 2 && endedParam.every(Number.isFinite) ? endedParam : null;

  return (
    <div className="flex flex-1 flex-col gap-6">
      {!inModal && (
        <Link href={`/schedule?week=${day}`} className="text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("back")}
        </Link>
      )}
      <div className="flex flex-col gap-2">
        <PageHeader
          title={<UserText className={cancelled ? "line-through" : ""}>{session.service.name}</UserText>}
          description={
            <>
              {formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })} ·{" "}
              <Ltr>
                {formatTime(session.starts_at, locale, tenant.time_zone)}-{formatTime(session.ends_at, locale, tenant.time_zone)}
              </Ltr>
              {cancelled && ` · ${t("cancelled")}`}
            </>
          }
        />
        {session.series_id && (
          <p className="text-sm text-muted">
            {t("series")} {session.series_open_ended && t("seriesOpen")}
          </p>
        )}
        <FormNotice message={ended ? t("seriesEnded", { cancelled: ended[0], kept: ended[1] }) : undefined} />
      </div>

      {reservation && session.price_amount != null && (
        <section aria-labelledby="payment-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="payment-heading" className="text-lg font-semibold">
            {session.room_name} · {formatMoney(session.price_amount, session.price_currency ?? tenant.currency, locale)}
          </h2>
          <p className={session.paid ? "font-medium text-success-ink" : "text-muted"}>{session.paid ? tResources("paid") : tResources("notPaid")}</p>
          {!session.paid && reservedBy && tenant.permissions.includes("sales.manage") && (
            <form action={recordVenuePayment.bind(null, session.id, reservedBy.id)} className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                {tResources("method")}
                <select name="method" defaultValue="cash" className="control px-3 py-2 font-normal">
                  {(["cash", "card", "transfer", "other"] as const).map((method) => (
                    <option key={method} value={method}>
                      {tResources(`methods.${method}`)}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="btn-primary px-4 py-2">
                {tResources("recordPayment")}
              </button>
            </form>
          )}
        </section>
      )}

      <JobPanel session={session} manageable={canManageBookings(tenant)} />

      <Roster
        session={session}
        context={context}
        manageable={canManageBookings(tenant)}
        search={(first(query.q) ?? "").trim()}
        error={first(query.error)}
      />

      {!reservation && (
        <section aria-labelledby="details-heading" className="flex flex-col gap-4 card p-6">
          <h2 id="details-heading" className="text-lg font-semibold">
            {t("details")}
          </h2>
          <SessionForm
            key={`${session.starts_at}-${session.ends_at}-${session.capacity}-${session.room_id}-${session.instructor_user_id}-${session.notes}`}
            action={updateSession.bind(null, session.id, session.series_id ? { id: session.series_id, date: day } : null)}
            options={options}
            defaults={{
              service_id: session.service.id,
              date: day,
              start_time: formatTime(session.starts_at, "en-GB", tenant.time_zone),
              duration_minutes: minutes,
              capacity: session.capacity,
              place: session.location_id ? `${session.location_id}:${session.room_id ?? ""}` : "",
              instructor_user_id: session.instructor_user_id,
              notes: session.notes,
            }}
            submitLabel={tCommon("save")}
            lockService
            readOnly={!writable}
            inSeries={!!session.series_id}
          />
        </section>
      )}

      {writable && session.series_id && session.series_open_ended && (
        <form action={endSeries.bind(null, session.series_id, session.id, day)}>
          <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
            {t("endSeries")}
          </button>
        </form>
      )}

      {writable && !reservation && (
        <SessionStatusButton
          sessionId={session.id}
          cancelled={cancelled}
          labels={{
            cancel: t("cancelSession"),
            restore: t("restoreSession"),
            cancelled: t("cancelledToast"),
            restored: t("restoredToast"),
            undo: tCommon("undo"),
          }}
        />
      )}
    </div>
  );
}
