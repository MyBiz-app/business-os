import type { components } from "@business-os/api-client";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import type { getTenant } from "@/lib/tenant";
import { unwrap } from "@/lib/api";

import { bookClient, setBookingStatus } from "../actions";

type Booking = components["schemas"]["Booking"];
type Session = components["schemas"]["ScheduledSession"];
type BookingStatus = Booking["status"];
type BookingAction = Exclude<BookingStatus, "waitlisted">;

const ERRORS = ["already_booked", "session_cancelled", "invalid_transition", "invalid_reference", "not_found"] as const;
type BookingErrorKey = (typeof ERRORS)[number];
const isKnownError = (value: string | undefined): value is BookingErrorKey =>
  ERRORS.includes(value as BookingErrorKey);

const TONE: Record<BookingStatus, string> = {
  booked: "bg-primary/15 text-primary",
  checked_in: "bg-success/15 text-success",
  waitlisted: "bg-border text-foreground",
  no_show: "bg-danger/15 text-danger",
  cancelled: "bg-border text-muted",
};

// Which status buttons each booking offers, in display order.
const NEXT_ACTIONS: Record<BookingStatus, BookingAction[]> = {
  booked: ["checked_in", "no_show", "cancelled"],
  checked_in: ["booked", "cancelled"],
  no_show: ["checked_in", "cancelled"],
  waitlisted: ["cancelled"],
  cancelled: [],
};

type Props = {
  session: Session;
  context: Awaited<ReturnType<typeof getTenant>>;
  manageable: boolean;
  search: string;
  error?: string;
};

export async function Roster({ session, context, manageable, search, error }: Props) {
  const t = await getTranslations("bookings");
  const { api, scope } = context;
  const bookings = unwrap(
    await api.GET("/sessions/{session_id}/bookings", {
      params: { ...scope, path: { session_id: session.id } },
    }),
  );
  const live = bookings.filter((b) => b.status !== "waitlisted" && b.status !== "cancelled");
  const waitlist = bookings.filter((b) => b.status === "waitlisted");
  const cancelled = bookings.filter((b) => b.status === "cancelled");
  const canBook = manageable && session.status === "scheduled";

  const bookedIds = new Set(bookings.filter((b) => b.status !== "cancelled").map((b) => b.client_id));
  const matches =
    canBook && search
      ? unwrap(
          await api.GET("/clients", { params: { ...scope, query: { search, status: "active", limit: 8 } } }),
        ).items.filter((client) => !bookedIds.has(client.id))
      : [];
  const full = session.booked >= session.capacity;

  const row = (booking: Booking) => (
    <li key={booking.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
      <div className="flex items-center gap-2">
        {booking.waitlist_position && (
          <span className="text-sm tabular-nums text-muted">{booking.waitlist_position}.</span>
        )}
        <Link href={`/clients/${booking.client_id}`} dir="auto" className="font-medium underline-offset-4 hover:underline">
          {booking.client_name}
        </Link>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONE[booking.status]}`}>
          {t(`statuses.${booking.status}`)}
        </span>
        {booking.late_cancel && <span className="text-xs text-danger">{t("lateCancel")}</span>}
        {booking.status !== "cancelled" &&
          (booking.plan_name ? (
            <span className="text-xs text-muted">{booking.plan_name}</span>
          ) : (
            <span className="rounded-full border border-danger/40 px-2 py-0.5 text-xs text-danger">{t("noPlan")}</span>
          ))}
      </div>
      {manageable && (
        <div className="flex flex-wrap gap-2">
          {NEXT_ACTIONS[booking.status].map((next) => (
            <form key={next} action={setBookingStatus.bind(null, session.id, booking.id, next)}>
              <button
                type="submit"
                aria-label={`${t(`actions.${next}`)} – ${booking.client_name}`}
                className={`rounded-lg border border-border px-2.5 py-1 text-xs font-medium hover:bg-surface ${next === "cancelled" ? "text-danger" : ""}`}
              >
                {t(`actions.${next}`)}
              </button>
            </form>
          ))}
        </div>
      )}
    </li>
  );

  return (
    <section aria-labelledby="roster-heading" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="roster-heading" className="text-lg font-semibold">
          {t("roster")}
        </h2>
        <p className="text-sm text-muted">
          {t("summary", { booked: session.booked, capacity: session.capacity, waitlisted: session.waitlisted })}
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          {isKnownError(error) ? t(`errors.${error}`) : t("errors.generic")}
        </p>
      )}

      {canBook && (
        <div className="flex flex-col gap-3">
          <form role="search" className="flex gap-2">
            <label htmlFor="roster-search" className="sr-only">
              {t("searchLabel")}
            </label>
            <input
              id="roster-search"
              name="q"
              type="search"
              defaultValue={search}
              placeholder={t("searchPlaceholder")}
              className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            <button type="submit" className="rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-background">
              {t("search")}
            </button>
          </form>
          {search && (
            <ul aria-label={t("results")} className="flex flex-col divide-y divide-border rounded-lg border border-border bg-background">
              {matches.length === 0 && <li className="px-3 py-2 text-sm text-muted">{t("noMatches")}</li>}
              {matches.map((client) => {
                const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
                return (
                  <li key={client.id} className="flex items-center justify-between gap-2 px-3 py-2">
                    <span dir="auto">{name}</span>
                    <form action={bookClient.bind(null, session.id, client.id)}>
                      <button
                        type="submit"
                        aria-label={`${full ? t("addToWaitlist") : t("book")} – ${name}`}
                        className="rounded-lg bg-primary px-3 py-1 text-xs font-medium text-on-primary"
                      >
                        {full ? t("addToWaitlist") : t("book")}
                      </button>
                    </form>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {live.length === 0 ? (
        <p className="text-sm text-muted">{t("empty")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">{live.map(row)}</ul>
      )}

      {waitlist.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-border pt-4">
          <h3 className="font-semibold">{t("waitlist")}</h3>
          <ul className="flex flex-col divide-y divide-border">{waitlist.map(row)}</ul>
        </div>
      )}

      {cancelled.length > 0 && (
        <details className="border-t border-border pt-4">
          <summary className="cursor-pointer text-sm text-muted">{t("cancelledCount", { count: cancelled.length })}</summary>
          <ul className="flex flex-col divide-y divide-border">{cancelled.map(row)}</ul>
        </details>
      )}
    </section>
  );
}
