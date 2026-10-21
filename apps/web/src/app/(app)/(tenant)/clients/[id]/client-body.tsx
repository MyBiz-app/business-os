import { CalendarPlus, Mail, MapPin, MessageCircle, Phone, RefreshCw, Tag } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AiScreen } from "../../ai-bubble/screen-context";
import { Avatar } from "@/components/avatar";
import { BackLink } from "@/components/back-link";
import { Ltr } from "@/components/bidi";
import { RecordHeader, type RecordStat } from "@/components/layout/record-header";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { RecordLayout, type RecordTab } from "@/components/record-layout";
import { ReviewsSummary } from "@/components/reviews-summary";
import { unwrap } from "@/lib/api";
import { formatTime, todayIn } from "@/lib/dates";
import { canSell, canWriteClients } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";
import { whatsappLink } from "@/lib/whatsapp";
import { vertical } from "@business-os/verticals";

import { updateClient } from "../actions";
import { ClientForm } from "../client-form";
import { StatusBadge } from "../status-badge";
import { ActivitySection } from "./activity-section";
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
const STATUS_TONE: Record<"booked" | "waitlisted" | "checked_in" | "no_show" | "cancelled", BadgeTone> = {
  booked: "primary",
  waitlisted: "warning",
  checked_in: "success",
  no_show: "danger",
  cancelled: "neutral",
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
  // The one thing to do next: sell a plan, renew one that is ending (both for those who sell), or
  // book a visit for a client with nothing coming up.
  async function findNextAction(): Promise<"sell" | "renew" | "book" | null> {
    if (erased) return null;
    const selling = canSell(tenant);
    const plans = selling
      ? unwrap(await api.GET("/clients/{client_id}/entitlements", { params: { ...scope, path: { client_id: id } } }))
      : [];
    const live = plans.filter((plan) => ["active", "upcoming", "frozen"].includes(plan.state));
    if (selling && live.length === 0) return "sell";
    const soon = new Date(`${todayIn(tenant.time_zone)}T00:00:00Z`);
    soon.setUTCDate(soon.getUTCDate() + 7);
    const ending = live.some(
      (plan) =>
        plan.state === "active" &&
        (Date.parse(`${plan.ends_on}T00:00:00Z`) <= soon.getTime() ||
          (plan.kind === "punch_card" && plan.credits_remaining !== null && plan.credits_remaining <= 1)),
    );
    if (selling && ending) return "renew";
    if (canWriteClients(tenant) && upcoming.every((b) => b.status !== "booked")) return "book";
    return null;
  }
  // Visits given back to this client (an exception, so it is counted): only for those who sell.
  const waivers = canSell(tenant)
    ? unwrap(await api.GET("/clients/{client_id}/waivers", { params: { ...scope, path: { client_id: id } } }))
    : null;
  const nextAction = await findNextAction();
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
          <Badge tone={booking.session_status === "cancelled" ? "neutral" : STATUS_TONE[booking.status]}>
            {booking.session_status === "cancelled"
              ? tBookings("sessionCancelled")
              : tBookings(`statuses.${booking.status}`)}
            {booking.late_cancel && ` · ${tBookings("lateCancel")}`}
          </Badge>
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
  const stats: RecordStat[] = [
    { key: "visits", label: t("profile.stats.visits"), value: number.format(attended.length) },
    {
      key: "lastVisit",
      label: t("profile.stats.lastVisit"),
      value: lastVisit
        ? new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone }).format(new Date(lastVisit.starts_at))
        : t("profile.never"),
    },
    { key: "upcoming", label: t("profile.stats.upcoming"), value: number.format(upcoming.filter((b) => b.status === "booked").length) },
    { key: "noShows", label: t("profile.stats.noShows"), value: number.format(noShows) },
    ...(reviews.count > 0 && reviews.average !== null
      ? [{ key: "rating", label: t("profile.stats.rating"), value: new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(reviews.average) }]
      : []),
  ];
  // Time and monthly billing (#45): for industries that bill by time (their pack says so).
  const workSections = vertical(tenant.vertical)?.timeBilling ?? false;
  const whatsapp = client.phone ? whatsappLink(client.phone, tenant.time_zone) : null;
  const tConsent = await getTranslations("clients.consent");
  const showPrivacy = !erased || reviews.count > 0;

  // The tabs of the card, in the order a person works through it.
  const tabs: RecordTab[] = [
    {
      id: "details",
      label: t("nav.details"),
      content: (
        <>
          <Card as="section" aria-labelledby="details-heading">
            <CardHeader title={t("details")} titleId="details-heading" />
            <ClientForm
              action={updateClient.bind(null, client.id)}
              client={client}
              submitLabel={t("save")}
              readOnly={!writable}
              branches={branches}
            />
          </Card>

          <DependentsSection clientId={client.id} context={context} locked={erased} />

          <AddressesSection clientId={client.id} context={context} locked={erased} />

          <ProfileSection clientId={client.id} values={client.custom_fields} context={context} locked={erased} />
        </>
      ),
    },
    {
      id: "membership",
      label: t("nav.membership"),
      content: (
        <>
          <PlansSection clientId={client.id} context={context} locked={erased} />

          <Card as="section" aria-labelledby="bookings-heading" className="flex flex-col gap-4">
            <h2 id="bookings-heading" className="text-lg font-semibold">
              {tBookings("title")}
            </h2>
            {bookings.length === 0 && <p className="text-sm text-muted">{tBookings("noneYet")}</p>}
            {waivers && waivers.items.length > 0 && (
              <CollapsibleSection variant="inline" className="rounded-xl bg-primary-subtle p-3 text-sm" triggerClassName="font-medium text-primary-ink" title={tBookings("waive.thisYear", { count: waivers.this_year })}>
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
          </Card>
        </>
      ),
    },
    {
      id: "paperwork",
      label: t("nav.paperwork"),
      content: (
        <>
          <QuotesSection clientId={client.id} context={context} locked={erased} />

          {workSections && <TimeSection clientId={client.id} context={context} locked={erased} />}

          <DocumentsSection clientId={client.id} context={context} locked={erased} />
        </>
      ),
    },
    {
      id: "talk",
      label: t("nav.talk"),
      content: (
        <>
          <NotesSection clientId={client.id} bookings={bookings} context={context} locked={erased} />

          <MessagesSection
            target={{ client_id: client.id }}
            phone={client.phone}
            path={`/clients/${client.id}`}
            context={context}
            locked={erased}
          />
        </>
      ),
    },
    {
      id: "activity",
      label: t("nav.activity"),
      content: <ActivitySection clientId={client.id} context={context} />,
    },
    ...(showPrivacy
      ? [
          {
            id: "privacy",
            label: t("nav.privacy"),
            content: (
              <>
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
              </>
            ),
          },
        ]
      : []),
  ];

  // Fixed facts at a glance, beside the tabs on a wide page (a window over the list has no room for it).
  const aside = inModal ? undefined : (
    <Card as="section" aria-labelledby="glance-heading">
      <CardHeader title={t("glance")} titleId="glance-heading" className="mb-3" />
      <dl className="flex flex-col gap-3 text-sm">
        {!erased && client.phone && (
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted">{t("phone")}</dt>
            <dd>
              <Ltr>{client.phone}</Ltr>
            </dd>
          </div>
        )}
        {!erased && client.email && (
          <div className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-xs text-muted">{t("email")}</dt>
            <dd className="truncate">
              <Ltr>{client.email}</Ltr>
            </dd>
          </div>
        )}
        {home && (
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted">{t("homeBranch")}</dt>
            <dd>
              <UserText>{home.name}</UserText>
            </dd>
          </div>
        )}
        {!erased && (
          <div className="flex flex-col gap-1">
            <dt className="text-xs text-muted">{tConsent("title")}</dt>
            <dd>
              <Badge tone={client.marketing_consent ? "success" : "neutral"} dot>
                {client.marketing_consent ? tConsent("on") : tConsent("off")}
              </Badge>
            </dd>
          </div>
        )}
      </dl>
    </Card>
  );

  return (
    <div className="flex flex-1 flex-col gap-6">
      <AiScreen label={tBubble("screenClient", { name })} />
      {!inModal && <BackLink href="/clients" label={t("back")} />}

      <RecordHeader
        avatar={<Avatar id={client.id} name={name} size="lg" />}
        name={name}
        inModal={inModal}
        badges={
          <>
            <StatusBadge status={client.status} />
            {client.is_staff && <Badge tone="primary">{t("staffBadge")}</Badge>}
          </>
        }
        subtitle={
          <>
            <span>{t("joined", { date: joined })}</span>
            {home && (
              <span className="flex items-center gap-1">
                <MapPin aria-hidden="true" className="size-3.5" />
                <UserText>{home.name}</UserText>
              </span>
            )}
          </>
        }
        actions={
          <>
            {nextAction === "book" ? (
              <ButtonLink href="/schedule" variant="primary">
                <CalendarPlus aria-hidden="true" className="size-4" /> {t("nextAction.book")}
              </ButtonLink>
            ) : nextAction ? (
              <ButtonLink href="#membership" variant="primary">
                {nextAction === "sell" ? <Tag aria-hidden="true" className="size-4" /> : <RefreshCw aria-hidden="true" className="size-4" />}{" "}
                {t(`nextAction.${nextAction}`)}
              </ButtonLink>
            ) : null}
            {!erased && (client.phone || client.email) ? (
            <nav aria-label={t("profile.contact")} className="flex flex-wrap items-center gap-2">
              {client.phone && (
                <ButtonLink href={`tel:${client.phone}`} variant="secondary">
                  <Phone aria-hidden="true" className="size-4" /> {t("profile.call")}
                </ButtonLink>
              )}
              {whatsapp && (
                <ButtonLink href={whatsapp} target="_blank" rel="noreferrer" variant="secondary">
                  <MessageCircle aria-hidden="true" className="size-4" /> WhatsApp
                </ButtonLink>
              )}
              {client.email && (
                <ButtonLink href={`mailto:${client.email}`} variant="secondary">
                  <Mail aria-hidden="true" className="size-4" /> {t("profile.email")}
                </ButtonLink>
              )}
            </nav>
            ) : null}
          </>
        }
        stats={stats}
      />

      {!erased && client.email_suppressed && (
        <p role="status" className="rounded-xl border border-border bg-warning-soft px-4 py-3 text-sm">
          {t("profile.emailUnreachable")}
        </p>
      )}

      {client.erased_at && (
        <p role="status" className="rounded-xl border border-border bg-surface px-4 py-3 text-sm">
          {tPrivacy("erasedOn", {
            date: new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
              new Date(client.erased_at),
            ),
          })}
        </p>
      )}

      <RecordLayout tabs={tabs} label={t("nav.label")} aside={aside} />
    </div>
  );
}
