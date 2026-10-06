import type { components } from "@business-os/api-client";
import { MapPin, Navigation } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Pill, type Tone } from "@/components/pill";
import { googleMapsLink, wazeLink } from "@/lib/maps";

import { setJobStatus } from "../actions";

type Session = components["schemas"]["ScheduledSession"];
type JobStatus = NonNullable<Session["job_status"]>;

const STEPS: JobStatus[] = ["scheduled", "on_the_way", "in_progress", "done"];
const TONE: Record<JobStatus, Tone> = { scheduled: "muted", on_the_way: "warning", in_progress: "primary", done: "success" };

/** An on-site job (#42): where, how to get in, navigation, and its progress. */
export async function JobPanel({ session, manageable }: { session: Session; manageable: boolean }) {
  const t = await getTranslations("jobs");
  const status = session.job_status;
  if (!status) return null;
  const index = STEPS.indexOf(status);
  const next = STEPS[index + 1];
  const previous = STEPS[index - 1];
  const live = session.status === "scheduled";

  return (
    <section aria-labelledby="job-heading" className="card flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="job-heading" className="flex items-center gap-2 text-lg font-semibold">
          <MapPin aria-hidden="true" className="size-5 text-primary" />
          {t("title")}
        </h2>
        <Pill tone={TONE[status]}>{t(`statuses.${status}`)}</Pill>
      </div>
      {session.address ? (
        <div className="flex flex-col gap-1">
          <p dir="auto" className="font-medium">{session.address}</p>
          {session.address_notes && <p dir="auto" className="text-sm text-muted">{session.address_notes}</p>}
          {session.travel_minutes > 0 && <p className="text-sm text-muted">{t("travelBefore", { minutes: session.travel_minutes })}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            <a href={wazeLink(session.address)} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-1.5 text-sm">
              <Navigation aria-hidden="true" className="size-4" /> Waze
            </a>
            <a href={googleMapsLink(session.address)} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-1.5 text-sm">
              <Navigation aria-hidden="true" className="size-4" /> Google Maps
            </a>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted">{t("noAddress")}</p>
      )}
      <ol aria-label={t("progress")} className="flex flex-wrap items-center gap-2 text-sm">
        {STEPS.map((step, i) => (
          <li
            key={step}
            aria-current={step === status ? "step" : undefined}
            className={`rounded-full px-3 py-1 ${i <= index ? "bg-primary/15 font-semibold text-foreground" : "bg-foreground/5 text-muted"}`}
          >
            {t(`statuses.${step}`)}
          </li>
        ))}
      </ol>
      {manageable && live && (
        <div className="flex flex-wrap gap-2">
          {next && (
            <form action={setJobStatus.bind(null, session.id, next)}>
              <button type="submit" className="btn-primary px-4 py-2 text-sm">
                {t(`actions.${next as Exclude<JobStatus, "scheduled">}`)}
              </button>
            </form>
          )}
          {previous && (
            <form action={setJobStatus.bind(null, session.id, previous)}>
              <button type="submit" className="btn-secondary px-4 py-2 text-sm">
                {t("undo")}
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
