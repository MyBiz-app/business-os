import { CalendarCheck, CalendarClock, History, Mail, MapPin, MessageCircle, Phone, Star, UserX } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AiScreen } from "../../ai-bubble/screen-context";
import { Avatar } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { Pill, type Tone } from "@/components/pill";
import { RecordLayout } from "@/components/record-layout";
import { ReviewsSummary } from "@/components/reviews-summary";
import type { SectionNavItem } from "@/components/section-nav";
import { unwrap } from "@/lib/api";
import { formatTime } from "@/lib/dates";
import { canSell, canWriteClients } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";
import { whatsappLink } from "@/lib/whatsapp";
import { vertical } from "@business-os/verticals";

import { updateClient } from "../actions";
import { ClientForm } from "../client-form";
import { StatusBadge } from "../status-badge";
import { AddressesSection } from "./addresses-section";
import { ConsentSection } from "./consent-section";
import { DependentsSection } from "./dependents-section";
import { HealthSection } from "./health-section";
import { IdentitySection } from "./identity-section";
import { PlansSection } from "./plans-section";
import { PrivacySection } from "./privacy-section";
import { UserText } from "@/components/bidi";
import { QuotesSection } from "./quotes-section";
import { DocumentsSection, TimeSection } from "./work-section";
import { MessagesSection } from "../../messages/messages-section";
import { NotesSection, ProfileSection } from "./profile-section";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

/** Bookings arrive newest first; upcoming ones are shown soonest first. */
const RECENT = 8; // past visits shown before "show the whole history"
const STATUS_TONE: Record<"booked" | "waitlisted" | "checked_in" | "no_show" | "cancelled", Tone> = {
  booked: "primary",
  waitlisted: "warning",
  checked_in: "success",
  no_show: "danger",
  cancelled: "muted",
};

function splitByNow<T extends { starts_at: string }>(bookings: T[]) {
  const now = Date.now();
  return {
    upcoming: bookings.filter((b) => Date.parse(b.starts_at) >= now).reverse(),
    past: bookings.filter((b) => Date.parse(b.starts_at) < now),
  };
}

/** One client: the page and the window over the clients list show the same thing. */
export async function ClientBody({ id, inModal = false }: { id: string; inModal?: boolean }) {
  const t = await getTranslations("clients");
  const tBookings = await getTranslations("bookings");
  const tPrivacy = await getTranslations("privacy");
  const tBubble = await getTranslations("aiBubble");
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
  // Visits given back to this client (an exception, so it is counted): only for those who sell.
  const waivers = canSell(tenant)
    ? unwrap(await api.GET("/clients/{client_id}/waivers", { params: { ...scope, path: { client_id: id } } }))
    : null;
  const consentEvents = unwrap(
    await api.GET("/clients/{client_id}/consent-events", { params: { ...scope, path: { client_id: id } } }),
  );
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
            <span className="font-medium">
              {booking.service_name}
              {booking.dependent_name && (
                <span dir="auto" className="font-normal text-muted">
                  {" "}
                  · {booking.dependent_name}
                </span>
              )}
            </span>
            <span className="text-sm text-muted">
              {dateFormat.format(new Date(booking.starts_at))} ·{" "}
              <span dir="ltr">{formatTime(booking.starts_at, locale, tenant.time_zone)}</span>
            </span>
          </Link>
          <Pill tone={booking.session_status === "cancelled" ? "muted" : STATUS_TONE[booking.status]}>
            {booking.session_status === "cancelled"
              ? tBookings("sessionCancelled")
              : tBookings(`statuses.${booking.status}`)}
            {booking.late_cancel && ` · ${tBookings("lateCancel")}`}
          </Pill>
        </li>
      ))}
    </ul>
  );

  const name = [client.first_name, client.last_name].filter(Boolean).join(" ");
  const branches = await getBranches();
  const home = branches.find((branch) => branch.id === client.home_location_id);
  const attended = past.filter((b) => b.status === "checked_in");
  const noShows = past.filter((b) => b.status === "no_show").length;
  const lastVisit = attended[0];
  const number = new Intl.NumberFormat(locale);
  type Stat = { key: "visits" | "lastVisit" | "upcoming" | "noShows" | "rating"; Icon: typeof Star; value: string };
  const stats: Stat[] = [
    { key: "visits", Icon: CalendarCheck, value: number.format(attended.length) },
    {
      key: "lastVisit",
      Icon: History,
      value: lastVisit
        ? new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone }).format(new Date(lastVisit.starts_at))
        : t("profile.never"),
    },
    { key: "upcoming", Icon: CalendarClock, value: number.format(upcoming.filter((b) => b.status === "booked").length) },
    { key: "noShows", Icon: UserX, value: number.format(noShows) },
    ...(reviews.count > 0 && reviews.average !== null
      ? [{ key: "rating" as const, Icon: Star, value: new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(reviews.average) }]
      : []),
  ];
  // Time and monthly billing (#45): for industries that bill by time (their pack says so).
  const workSections = vertical(tenant.vertical)?.timeBilling ?? false;
  const whatsapp = client.phone ? whatsappLink(client.phone, tenant.time_zone) : null;

  // The inner menu of the card, in the order the sections follow.
  const showPrivacy = !erased || reviews.count > 0;
  const menu: SectionNavItem[] = [
    { id: "details", label: t("nav.details") },
    { id: "membership", label: t("nav.membership") },
    { id: "paperwork", label: t("nav.paperwork") },
    { id: "talk", label: t("nav.talk") },
    ...(showPrivacy ? [{ id: "privacy", label: t("nav.privacy") }] : []),
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <AiScreen label={tBubble("screenClient", { name })} />
      {!inModal && (
        <BackLink href="/clients" label={t("back")} />
      )}

      <header className="card-accent flex flex-col gap-5 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-4">
            <Avatar id={client.id} name={name} size="lg" />
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 dir="auto" className="truncate text-3xl font-extrabold tracking-tight">{name}</h1>
                <StatusBadge status={client.status} />
                {client.is_staff && <Pill tone="primary">{t("staffBadge")}</Pill>}
              </div>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
                <span>{t("joined", { date: joined })}</span>
                {home && (
                  <span className="flex items-center gap-1">
                    <MapPin aria-hidden="true" className="size-3.5" />
                    <UserText>{home.name}</UserText>
                  </span>
                )}
              </p>
            </div>
          </div>
          {!erased && (client.phone || client.email) && (
            <nav aria-label={t("profile.contact")} className="flex flex-wrap gap-2">
              {client.phone && (
                <a href={`tel:${client.phone}`} className="btn-secondary px-3 py-2 text-sm">
                  <Phone aria-hidden="true" className="size-4" /> {t("profile.call")}
                </a>
              )}
              {whatsapp && (
                <a href={whatsapp} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-2 text-sm">
                  <MessageCircle aria-hidden="true" className="size-4" /> WhatsApp
                </a>
              )}
              {client.email && (
                <a href={`mailto:${client.email}`} className="btn-secondary px-3 py-2 text-sm">
                  <Mail aria-hidden="true" className="size-4" /> {t("profile.email")}
                </a>
              )}
            </nav>
          )}
        </div>
        {!erased && client.email_suppressed && (
          <p role="status" className="rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-muted">
            {t("profile.emailUnreachable")}
          </p>
        )}
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {stats.map(({ key, Icon, value }) => (
            <li key={key} className="flex items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3">
              <span aria-hidden="true" className="icon-tile size-9">
                <Icon className="size-4" />
              </span>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-xs text-muted">{t(`profile.stats.${key}`)}</span>
                <span className="truncate text-lg font-bold">{value}</span>
              </div>
            </li>
          ))}
        </ul>
      </header>

      {client.erased_at && (
        <p role="status" className="rounded-lg border border-border bg-surface px-4 py-3 text-sm">
          {tPrivacy("erasedOn", {
            date: new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
              new Date(client.erased_at),
            ),
          })}
        </p>
      )}

      <RecordLayout items={menu} label={t("nav.label")} menu={!inModal}>
        <div id="details" className="flex flex-col gap-6">
          <section aria-labelledby="details-heading" className="card p-6">
            <h2 id="details-heading" className="mb-4 text-lg font-semibold">
              {t("details")}
            </h2>
            <ClientForm
              action={updateClient.bind(null, client.id)}
              client={client}
              submitLabel={t("save")}
              readOnly={!writable}
              branches={branches}
            />
          </section>

          <DependentsSection clientId={client.id} context={context} locked={erased} />

          <AddressesSection clientId={client.id} context={context} locked={erased} />

          <ProfileSection clientId={client.id} values={client.custom_fields} context={context} locked={erased} />
        </div>

        <div id="membership" className="flex flex-col gap-6">
          <PlansSection clientId={client.id} context={context} locked={erased} />

          <section aria-labelledby="bookings-heading" className="flex flex-col gap-4 card p-6">
            <h2 id="bookings-heading" className="text-lg font-semibold">
              {tBookings("title")}
            </h2>
            {bookings.length === 0 && <p className="text-sm text-muted">{tBookings("noneYet")}</p>}
            {waivers && waivers.items.length > 0 && (
              <CollapsibleSection variant="inline" className="rounded-xl bg-primary/5 p-3 text-sm" triggerClassName="font-medium text-primary-ink" title={tBookings("waive.thisYear", { count: waivers.this_year })}>
                <ul className="flex flex-col gap-1 text-muted">
                  {waivers.items.map((item) => (
                    <li key={item.booking_id}>
                      {item.service_name} · {dateFormat.format(new Date(item.starts_at))}
                      {item.reason && ` · ${item.reason}`}
                      {item.waived_by_name && ` · ${item.waived_by_name}`}
                    </li>
                  ))}
                </ul>
              </CollapsibleSection>
            )}
            {upcoming.length > 0 && (
              <div className="flex flex-col gap-1">
                <h3 className="font-semibold">{tBookings("upcoming")}</h3>
                {bookingList(upcoming)}
              </div>
            )}
            {past.length > 0 && (
              <div className="flex flex-col gap-1">
                <h3 className="font-semibold">{tBookings("history")}</h3>
                {bookingList(past.slice(0, RECENT))}
                {past.length > RECENT && (
                  <CollapsibleSection variant="inline" title={tBookings("showAll", { count: past.length })}>
                    {bookingList(past.slice(RECENT))}
                  </CollapsibleSection>
                )}
              </div>
            )}
          </section>
        </div>

        <div id="paperwork" className="flex flex-col gap-6">
          <QuotesSection clientId={client.id} context={context} locked={erased} />

          {workSections && <TimeSection clientId={client.id} context={context} locked={erased} />}

          <DocumentsSection clientId={client.id} context={context} locked={erased} />
        </div>

        <div id="talk" className="flex flex-col gap-6">
          <NotesSection clientId={client.id} bookings={bookings} context={context} locked={erased} />

          <MessagesSection
            target={{ client_id: client.id }}
            phone={client.phone}
            path={`/clients/${client.id}`}
            context={context}
            locked={erased}
          />
        </div>

        {showPrivacy && (
          <div id="privacy" className="flex flex-col gap-6">
            {!erased && <ConsentSection clientId={client.id} consent={client.marketing_consent} optedOut={client.marketing_opted_out_at != null} events={consentEvents} canWrite={canWriteClients(tenant)} />}

            {!erased && tenant.client_id_number !== "off" && <IdentitySection clientId={client.id} />}

            {!erased && tenant.requires_health_declaration && <HealthSection clientId={client.id} context={context} />}

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

            {!erased && tenant.permissions.includes("clients.privacy") && <PrivacySection clientId={client.id} name={name} />}
          </div>
        )}
      </RecordLayout>
    </div>
  );
}
