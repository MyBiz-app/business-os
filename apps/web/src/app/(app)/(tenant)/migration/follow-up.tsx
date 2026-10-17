"use client";

import { useTranslations } from "next-intl";
import { useEffect, useId, useState, useTransition } from "react";

import {
  askConcierge,
  getFollowUp,
  sendNotice,
  type ConciergeResult,
  type FollowUp,
  type NoticeChannel,
  type NoticeResult,
} from "./actions";

const CHANNELS: NoticeChannel[] = ["email", "push", "popup"];
const WEEK_STEPS = ["keep", "compare", "announce", "cancel"] as const;
const HOURS = [24, 48, 72];
const CONTROL = "w-full min-w-0 control px-3 py-2";

type Lookup = (group: string, key: string, fallback: string) => string;

function useFollowUp(sessionId: string) {
  const [data, setData] = useState<FollowUp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let current = true;
    void getFollowUp(sessionId).then((result) => {
      if (!current) return;
      if (result.data) setData(result.data);
      else setError(result.error ?? "generic");
    });
    return () => {
      current = false;
    };
  }, [sessionId, version]);
  return { data, error, load: async () => setVersion((v) => v + 1) };
}

function useWord(): Lookup {
  const t = useTranslations("migration");
  const lookup = t as unknown as ((key: string) => string) & { has: (key: string) => boolean };
  return (group, key, fallback) => (lookup.has(`${group}.${key}`) ? lookup(`${group}.${key}`) : fallback);
}

function ErrorLine({ error }: { error: string }) {
  const t = useTranslations("migration");
  const word = useWord();
  return (
    <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
      {word("errors", error, t("errors.generic"))}
    </p>
  );
}

/** "Do it for me" on its own, for a move that is still being prepared. */
export function ConciergePanel({ sessionId, timeZone }: { sessionId: string; timeZone: string }) {
  const { data, error, load } = useFollowUp(sessionId);
  const word = useWord();
  const date = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone });
  if (!data) return error ? <ErrorLine error={error} /> : null;
  return <ConciergeCard sessionId={sessionId} data={data} date={date} word={word} onAsked={load} />;
}

/** After the import (round 6, M3): tell the moved clients, run the parallel week, or ask the MyBiz
 * team to do the move for the business. */
export function FollowUpPanel({ sessionId, timeZone }: { sessionId: string; timeZone: string }) {
  const word = useWord();
  const { data, error, load } = useFollowUp(sessionId);
  const date = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone });

  if (!data) return error ? <ErrorLine error={error} /> : null;

  return (
    <div className="flex flex-col gap-6">
      <NoticeCard sessionId={sessionId} data={data} date={date} word={word} onSent={load} />
      <WeekCard sessionId={sessionId} />
      <ConciergeCard sessionId={sessionId} data={data} date={date} word={word} onAsked={load} />
    </div>
  );
}

function NoticeCard({
  sessionId,
  data,
  date,
  word,
  onSent,
}: {
  sessionId: string;
  data: FollowUp;
  date: Intl.DateTimeFormat;
  word: Lookup;
  onSent: () => Promise<void>;
}) {
  const t = useTranslations("migration");
  const raw = (key: string) => (t.raw as (key: string) => unknown)(key) as string;
  const subjectId = useId();
  const bodyId = useId();
  const [pending, startTransition] = useTransition();
  const [subject, setSubject] = useState(() => t("followUp.defaultSubject"));
  const [body, setBody] = useState(() => raw("followUp.defaultBody"));
  const [channels, setChannels] = useState<NoticeChannel[]>(["email"]);
  const [resend, setResend] = useState(false);
  const [result, setResult] = useState<NoticeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const alreadySent = Boolean(data.notice_sent_at);
  const run = (dryRun: boolean) =>
    startTransition(async () => {
      setError(null);
      const response = await sendNotice(sessionId, { subject, body, channels, resend }, dryRun);
      if (!response.data) {
        setError(response.error ?? "generic");
        return;
      }
      setResult(response.data);
      if (!dryRun) await onSent();
    });
  // Any edit makes the earlier preview stale.
  const edit = <T,>(set: (value: T) => void) => (value: T) => {
    set(value);
    setResult((current) => (current?.sent ? current : null));
  };

  const channelWord = (channel: string) => word("followUp.channels", channel, channel);

  return (
    <section aria-labelledby="notice-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="notice-heading" className="text-lg font-semibold">{t("followUp.title")}</h2>
        <p className="text-sm text-muted">{t("followUp.intro")}</p>
        <p className="text-sm">
          {t("followUp.summary", { count: data.clients, email: data.with_email, phone: data.with_phone_only })}
        </p>
      </div>

      {data.clients === 0 ? (
        <p className="text-sm text-muted">{t("errors.no_clients")}</p>
      ) : (
        <>
          {alreadySent && data.notice_sent_at && (
            <p role="status" className="rounded-lg bg-surface-2 px-3 py-2 text-sm">
              {t("followUp.sentOn", { date: date.format(new Date(data.notice_sent_at)), count: data.notice_recipients ?? 0 })}
            </p>
          )}

          <div className="flex flex-col gap-1">
            <label htmlFor={subjectId} className="text-sm font-medium">{t("followUp.subjectLabel")}</label>
            <input
              id={subjectId}
              value={subject}
              maxLength={150}
              dir="auto"
              className={CONTROL}
              onChange={(event) => edit(setSubject)(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={bodyId} className="text-sm font-medium">{t("followUp.bodyLabel")}</label>
            <textarea
              id={bodyId}
              value={body}
              maxLength={1000}
              rows={6}
              dir="auto"
              className={CONTROL}
              aria-describedby={`${bodyId}-hint`}
              onChange={(event) => edit(setBody)(event.target.value)}
            />
            <p id={`${bodyId}-hint`} className="text-sm text-muted">{raw("followUp.bodyHint")}</p>
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">{t("followUp.channelsLabel")}</legend>
            <div className="flex flex-wrap gap-4">
              {CHANNELS.map((channel) => (
                <label key={channel} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={channels.includes(channel)}
                    disabled={channels.length === 1 && channels.includes(channel)}
                    onChange={(event) =>
                      edit(setChannels)(
                        event.target.checked ? [...channels, channel] : channels.filter((c) => c !== channel),
                      )
                    }
                  />
                  {channelWord(channel)}
                </label>
              ))}
            </div>
            <p className="text-sm text-muted">{t("followUp.channelsHint")}</p>
          </fieldset>

          {error && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {word("errors", error, t("errors.generic"))}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-secondary px-4 py-2.5" disabled={pending} aria-busy={pending} onClick={() => run(true)}>
              {pending && !result ? t("followUp.previewing") : t("followUp.preview")}
            </button>
            {result && !result.sent && result.recipients > 0 && (
              <button
                type="button"
                className="btn-primary px-4 py-2.5"
                disabled={pending || (alreadySent && !resend)}
                aria-busy={pending}
                onClick={() => run(false)}
              >
                {pending ? t("followUp.sending") : t("followUp.send", { count: result.recipients })}
              </button>
            )}
            {alreadySent && result && !result.sent && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4" checked={resend} onChange={(event) => setResend(event.target.checked)} />
                {t("followUp.resend")}
              </label>
            )}
          </div>

          {result?.sent && (
            <p role="status" className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{t("followUp.sentNow")}</p>
          )}

          {result && !result.sent && (
            <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3 text-sm">
              <p className="font-medium">
                {t("followUp.reach", {
                  count: result.recipients,
                  channels: Object.entries(result.by_channel)
                    .map(([channel, count]) => t("followUp.channelCount", { channel: channelWord(channel), count }))
                    .join(", "),
                })}
              </p>
              {result.preview && (
                <>
                  <p className="text-muted">{t("followUp.previewTitle")}</p>
                  <p className="whitespace-pre-wrap" dir="auto">{result.preview}</p>
                </>
              )}
              {result.warnings.map((warning) => (
                <p key={warning.variable} className="text-warning">
                  {t("followUp.missing", {
                    count: warning.recipients,
                    variable: warning.variable,
                    example: `{${warning.variable}|…}`,
                  })}
                </p>
              ))}
            </div>
          )}

          {result && result.phone_only_total > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold">{t("followUp.phoneOnlyTitle")}</h3>
              <p className="text-sm text-muted">{t("followUp.phoneOnlyHint")}</p>
              <ul className="flex flex-col gap-2 text-sm">
                {result.phone_only.map((client) => (
                  <li key={client.client_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span dir="auto">{client.first_name} <span dir="ltr" className="text-muted">{client.phone}</span></span>
                    <span className="flex gap-2">
                      {client.whatsapp_link ? (
                        <a className="btn-secondary px-3 py-1.5" href={client.whatsapp_link} target="_blank" rel="noopener noreferrer">
                          {t("followUp.openWhatsapp")}
                        </a>
                      ) : (
                        <span className="text-muted">{t("followUp.noLink")}</span>
                      )}
                      <button
                        type="button"
                        className="btn-secondary px-3 py-1.5"
                        onClick={async () => {
                          await navigator.clipboard.writeText(client.text);
                          setCopied(client.client_id);
                        }}
                      >
                        {copied === client.client_id ? t("followUp.copied") : t("followUp.copyText")}
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
              {result.phone_only_total > result.phone_only.length && (
                <p className="text-sm text-muted">
                  {t("followUp.moreClients", { count: result.phone_only_total - result.phone_only.length })}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** The parallel week: a checklist the owner ticks off. Kept in this browser only. */
function WeekCard({ sessionId }: { sessionId: string }) {
  const t = useTranslations("migration");
  const key = `move-week-${sessionId}`;
  const [done, setDone] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(key) ?? "[]");
      return Array.isArray(saved) ? saved.filter((step): step is string => typeof step === "string") : [];
    } catch {
      return []; // storage may be blocked; the list just starts empty
    }
  });
  const toggle = (step: string, on: boolean) => {
    const next = on ? [...done, step] : done.filter((s) => s !== step);
    setDone(next);
    try {
      window.localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };
  return (
    <section aria-labelledby="week-heading" className="flex flex-col gap-3 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="week-heading" className="text-lg font-semibold">{t("followUp.weekTitle")}</h2>
        <p className="text-sm text-muted">{t("followUp.weekHint")}</p>
      </div>
      <ul className="flex flex-col gap-2">
        {WEEK_STEPS.map((step) => (
          <li key={step}>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 size-4"
                checked={done.includes(step)}
                onChange={(event) => toggle(step, event.target.checked)}
              />
              <span>{t(`followUp.week.${step}`)}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ConciergeCard({
  sessionId,
  data,
  date,
  word,
  onAsked,
}: {
  sessionId: string;
  data: FollowUp;
  date: Intl.DateTimeFormat;
  word: Lookup;
  onAsked: () => Promise<void>;
}) {
  const t = useTranslations("migration");
  const noteId = useId();
  const hoursId = useId();
  const [pending, startTransition] = useTransition();
  const [note, setNote] = useState("");
  const [hours, setHours] = useState(72);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ConciergeResult | null>(null);

  const requestedAt = data.concierge_requested_at ?? answer?.requested_at ?? null;
  const included = answer?.included ?? data.concierge_included;
  const until = answer?.support_until ?? data.support_until ?? null;

  return (
    <section aria-labelledby="concierge-heading" className="flex flex-col gap-3 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="concierge-heading" className="text-lg font-semibold">{t("followUp.conciergeTitle")}</h2>
        <p className="text-sm text-muted">{t("followUp.conciergeHint")}</p>
        <p className="text-sm">{included ? t("followUp.included") : t("followUp.quote")}</p>
      </div>
      {requestedAt ? (
        <div role="status" className="flex flex-col gap-1 rounded-lg bg-surface-2 px-3 py-2 text-sm">
          <p>{t("followUp.requestedOn", { date: date.format(new Date(requestedAt)) })}</p>
          {until && <p className="text-muted">{t("followUp.supportUntil", { date: date.format(new Date(until)) })}</p>}
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1">
            <label htmlFor={noteId} className="text-sm font-medium">{t("followUp.noteLabel")}</label>
            <textarea id={noteId} value={note} maxLength={1000} rows={3} dir="auto" className={CONTROL} onChange={(event) => setNote(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={hoursId} className="text-sm font-medium">{t("followUp.hoursLabel")}</label>
            <select id={hoursId} value={hours} className={CONTROL} onChange={(event) => setHours(Number(event.target.value))}>
              {HOURS.map((h) => (
                <option key={h} value={h}>{t("followUp.hours", { count: h })}</option>
              ))}
            </select>
          </div>
          {error && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {word("errors", error, t("errors.generic"))}
            </p>
          )}
          <div>
            <button
              type="button"
              className="btn-primary px-4 py-2.5"
              disabled={pending}
              aria-busy={pending}
              onClick={() =>
                startTransition(async () => {
                  setError(null);
                  const result = await askConcierge(sessionId, note, hours);
                  if (result.data) {
                    setAnswer(result.data);
                    await onAsked();
                  } else setError(result.error ?? "generic");
                })
              }
            >
              {pending ? t("followUp.asking") : t("followUp.ask")}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
