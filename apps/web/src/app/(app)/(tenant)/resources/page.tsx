import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { ReserveForm } from "./reserve-form";

const HOUR = 56; // pixels per hour in the day grid

/** Minutes since local midnight of an instant, in the business's time zone. */
function localMinutes(instant: string, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", { hour: "numeric", minute: "numeric", hourCycle: "h23", timeZone }).formatToParts(
    new Date(instant),
  );
  const part = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return part("hour") * 60 + part("minute");
}

const toMinutes = (clock: string) => Number(clock.slice(0, 2)) * 60 + Number(clock.slice(3, 5));

/** Courts and rooms rented by the hour: the day as a grid (courts × hours) with its
 * reservations, and a new reservation: service, length and day give the free times. */
export default async function ResourcesPage({ searchParams }: PageProps<"/resources">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope, branch } = await getTenantFor("schedule.read");
  const query = await searchParams;
  const param = (name: string) => (typeof query[name] === "string" ? (query[name] as string) : "");
  const today = todayIn(tenant.time_zone);
  const day = isDay(param("date")) ? param("date") : today;
  const zone = tenant.time_zone;

  const [locations, services, sessions] = await Promise.all([
    api.GET("/locations", { params: scope }).then(unwrap),
    api.GET("/resources", { params: scope }).then(unwrap),
    api.GET("/sessions", { params: { ...scope, query: { start: day, days: 1 } } }).then(unwrap),
  ]);
  const rooms = locations
    .filter((location) => location.active && (!branch || location.id === branch))
    .flatMap((location) => location.rooms.filter((room) => room.active && room.bookable));
  const hours = await Promise.all(
    rooms.map((room) => api.GET("/rooms/{room_id}/hours", { params: { ...scope, path: { room_id: room.id } } }).then(unwrap)),
  );
  const weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7; // 0 = Monday
  const open = new Map(hours.map((h) => [h.room_id, h.blocks.filter((b) => b.weekday === weekday)]));
  const inRooms = sessions.filter((s) => s.room_id && rooms.some((room) => room.id === s.room_id) && s.status === "scheduled");

  // The grid spans the day's opening hours (and anything booked outside them).
  const edges = [
    ...[...open.values()].flat().flatMap((b) => [toMinutes(b.starts), toMinutes(b.ends)]),
    ...inRooms.flatMap((s) => [localMinutes(s.starts_at, zone), localMinutes(s.ends_at, zone) || 24 * 60]),
  ];
  const first = edges.length ? Math.floor(Math.min(...edges) / 60) : 8;
  const last = edges.length ? Math.ceil(Math.max(...edges) / 60) : 22;
  const span = Math.max(last - first, 1);

  // A new reservation.
  const service = services.find((s) => s.id === param("service")) ?? services[0];
  const lengths = service ? Array.from({ length: (service.max_minutes - service.min_minutes) / service.step_minutes + 1 }, (_, i) => service.min_minutes + i * service.step_minutes) : [];
  const minutes = lengths.includes(Number(param("minutes"))) ? Number(param("minutes")) : (lengths[0] ?? 60);
  const search = param("q");
  const canBook = tenant.permissions.includes("bookings.manage");
  const [slots, clients] =
    canBook && service && service.rooms.length > 0 && day >= today
      ? await Promise.all([
          api.GET("/resources/slots", { params: { ...scope, query: { service_id: service.id, date: day, minutes } } }).then(unwrap),
          api.GET("/clients", { params: { ...scope, query: { limit: 20, status: "active", ...(search ? { search } : {}) } } }).then(unwrap),
        ])
      : [[], { items: [], total: 0 }];
  const dayLabel = formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" });
  const nav = (value: string) => `/resources?date=${value}${service ? `&service=${service.id}&minutes=${minutes}` : ""}`;

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("resources.title")}</h1>
          <p className="text-muted">{t("resources.subtitle")}</p>
        </div>
        <nav aria-label={t("resources.dayNav")} className="flex items-center gap-2 text-sm">
          <Link href={nav(addDays(day, -1))} className="btn-secondary px-3 py-2">
            {t("resources.previousDay")}
          </Link>
          {day !== today && (
            <Link href={nav(today)} className="btn-secondary px-3 py-2">
              {t("resources.today")}
            </Link>
          )}
          <Link href={nav(addDays(day, 1))} className="btn-secondary px-3 py-2">
            {t("resources.nextDay")}
          </Link>
        </nav>
      </div>

      {rooms.length === 0 ? (
        <p className="card p-6 text-muted">
          {t("resources.noBookableRooms")}{" "}
          <Link href="/locations" className="text-primary underline-offset-4 hover:underline">
            {t("resources.toLocations")}
          </Link>
        </p>
      ) : (
        <section aria-labelledby="grid-heading" className="card flex flex-col gap-4 p-4 sm:p-6">
          <h2 id="grid-heading" className="text-lg font-semibold">
            {dayLabel}
          </h2>
          <ScrollRegion labelledBy="grid-heading" className="pb-3">
            <div className="grid min-w-max gap-x-2" style={{ gridTemplateColumns: `3.5rem repeat(${rooms.length}, minmax(9rem, 1fr))` }}>
              <div />
              {rooms.map((room) => (
                <div key={room.id} className="truncate pb-2 text-center text-sm font-semibold">
                  {room.name}
                </div>
              ))}
              <div className="relative" style={{ height: span * HOUR }} aria-hidden="true">
                {Array.from({ length: span + 1 }, (_, i) => (
                  <span key={i} className="absolute end-1 -translate-y-1/2 text-xs text-muted tabular-nums" style={{ top: i * HOUR }} dir="ltr">
                    {String(first + i).padStart(2, "0")}:00
                  </span>
                ))}
              </div>
              {rooms.map((room) => (
                <ul
                  key={room.id}
                  aria-label={room.name}
                  // Closed hours are hatched; open hours are plain; a line marks every hour.
                  className="relative overflow-hidden rounded-xl border border-border"
                  style={{
                    height: span * HOUR,
                    backgroundImage: "repeating-linear-gradient(135deg, var(--border) 0, var(--border) 1px, transparent 1px, transparent 10px)",
                  }}
                >
                  {(open.get(room.id) ?? []).map((block) => (
                    <li
                      key={block.starts}
                      aria-hidden="true"
                      className="absolute inset-x-0 bg-surface"
                      style={{ top: ((toMinutes(block.starts) - first * 60) / 60) * HOUR, height: ((toMinutes(block.ends) - toMinutes(block.starts)) / 60) * HOUR }}
                    />
                  ))}
                  <li
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-0"
                    style={{
                      backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent ${HOUR - 1}px, var(--border) ${HOUR - 1}px, var(--border) ${HOUR}px)`,
                    }}
                  />
                  {inRooms
                    .filter((s) => s.room_id === room.id)
                    .map((s) => {
                      const start = localMinutes(s.starts_at, zone);
                      const end = localMinutes(s.ends_at, zone) || 24 * 60;
                      const label = s.booking_mode === "class" ? s.service.name : (s.appointment_client ?? s.service.name);
                      return (
                        <li
                          key={s.id}
                          className="absolute inset-x-1"
                          style={{ top: ((start - first * 60) / 60) * HOUR + 1, height: Math.max(((end - start) / 60) * HOUR - 2, 22) }}
                        >
                          <Link
                            href={`/schedule/${s.id}`}
                            className="flex h-full flex-col overflow-hidden rounded-lg border-s-4 bg-primary/15 px-2 py-1 text-xs hover:bg-primary/25"
                            style={{ borderColor: s.service.color ?? "var(--primary)" }}
                          >
                            <span className="truncate font-semibold" dir="auto">
                              {label}
                            </span>
                            <span className="tabular-nums text-muted" dir="ltr">
                              {formatTime(s.starts_at, locale, zone)}–{formatTime(s.ends_at, locale, zone)}
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                </ul>
              ))}
            </div>
          </ScrollRegion>
          {inRooms.length === 0 && <p className="text-sm text-muted">{t("resources.emptyDay")}</p>}
        </section>
      )}

      {canBook && rooms.length > 0 && (
        <section aria-labelledby="reserve-heading" className="card flex flex-col gap-5 p-6">
          <h2 id="reserve-heading" className="text-lg font-semibold">
            {t("resources.new")}
          </h2>
          {!service ? (
            <p className="text-muted">
              {t("resources.noServices")}{" "}
              <Link href="/services/new" className="text-primary underline-offset-4 hover:underline">
                {t("resources.addService")}
              </Link>
            </p>
          ) : (
            <>
              {/* Changing these reloads the free times (a plain GET form, works without JavaScript). */}
              <form method="get" className="grid gap-4 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  {t("resources.service")}
                  <select name="service" defaultValue={service.id} className="control px-3 py-2 font-normal">
                    {services.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} · {t("resources.perHour", { price: formatMoney(s.price_per_hour, s.price_currency, locale) })}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  {t("resources.length")}
                  <select name="minutes" defaultValue={minutes} className="control px-3 py-2 font-normal">
                    {lengths.map((value) => (
                      <option key={value} value={value}>
                        {t("services.minutes", { count: value })}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  {t("appointments.date")}
                  <input type="date" name="date" min={today} defaultValue={day} className="control px-3 py-2 font-normal" />
                </label>
                <button type="submit" className="btn-secondary px-4 py-2">
                  {t("appointments.show")}
                </button>
              </form>
              <form method="get" className="flex gap-2">
                <input type="hidden" name="service" value={service.id} />
                <input type="hidden" name="minutes" value={minutes} />
                <input type="hidden" name="date" value={day} />
                <label className="flex-1">
                  <span className="sr-only">{t("appointments.searchClient")}</span>
                  <input name="q" defaultValue={search} placeholder={t("appointments.searchClient")} className="control w-full px-3 py-2" />
                </label>
                <button type="submit" className="btn-secondary px-4 py-2">
                  {t("appointments.search")}
                </button>
              </form>
              {service.rooms.length === 0 ? (
                <p className="text-muted">{t("resources.noRoomsForService")}</p>
              ) : slots.length === 0 ? (
                <p className="text-muted">{day < today ? t("resources.pastDay") : t("resources.noSlots")}</p>
              ) : clients.items.length === 0 ? (
                <p className="text-muted">{t("resources.noClients")}</p>
              ) : (
                <ReserveForm
                  key={`${service.id}-${minutes}-${day}-${search}`}
                  serviceId={service.id}
                  minutes={minutes}
                  slots={slots
                    .filter((slot) => dayOf(slot.starts_at, zone) === day)
                    .map((slot) => ({
                      value: `${slot.room_id}|${slot.starts_at}`,
                      time: formatTime(slot.starts_at, locale, zone),
                      room: slot.room_name,
                      price: formatMoney(slot.price_amount, slot.price_currency, locale),
                    }))}
                  clients={clients.items.map((client) => ({
                    id: client.id,
                    name: [client.first_name, client.last_name].filter(Boolean).join(" "),
                    detail: client.phone ?? client.email ?? "",
                  }))}
                />
              )}
            </>
          )}
        </section>
      )}
    </main>
  );
}
