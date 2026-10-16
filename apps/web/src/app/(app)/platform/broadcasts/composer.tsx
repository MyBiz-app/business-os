"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import { useToast } from "@/components/toast/toaster";

import {
  type AudienceBody,
  type BroadcastBody,
  type BroadcastResult,
  cancelBroadcast,
  deleteBroadcast,
  previewAudience,
  type Preview,
  saveBroadcast,
  scheduleBroadcast,
  sendTest,
} from "./actions";

type Kind = BroadcastBody["kind"];
type Channel = BroadcastBody["channels"][number];
type Audience = Required<AudienceBody>;
type Group = Audience["groups"][number];
type Lang = "he" | "en";
type Texts = { subject: string; body: string; cta_label: string; cta_url: string; image_url: string };

const CHANNELS: Channel[] = ["email", "push", "popup", "whatsapp", "sms"];
const GROUPS: Group[] = ["team", "owners", "staff", "clients"];
const LANGS: Lang[] = ["he", "en"];
const TEMPLATES = ["feature", "promo", "maintenance", "version"] as const;
const BLANK: Texts = { subject: "", body: "", cta_label: "", cta_url: "", image_url: "" };

export type Initial = {
  id: string;
  kind: Kind;
  channels: Channel[];
  audience: Audience;
  content: Partial<Record<Lang, Partial<Texts>>>;
  status: string;
  scheduled_at: string | null;
};

type Option = { value: string; label: string };

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function Checks<T extends string>({ legend, hint, items, selected, onChange }: { legend: string; hint?: string; items: { value: T; label: string; hint?: string }[]; selected: T[]; onChange: (next: T[]) => void }) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium">{legend}</legend>
      {hint && <p className="text-xs text-muted">{hint}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <label key={item.value} className="flex items-start gap-2 rounded-xl border border-border p-3 text-sm">
            <input type="checkbox" checked={selected.includes(item.value)} onChange={() => onChange(toggle(selected, item.value))} className="mt-0.5 size-4 accent-[var(--primary)]" />
            <span className="flex flex-col">
              <span className="font-medium">{item.label}</span>
              {item.hint && <span className="text-xs text-muted">{item.hint}</span>}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Writes or edits a message: type, channels, audience (with a live count), the words in each
 * language, and when it goes out. A scheduled message is edited as a draft again. */
export function Composer({ initial, verticals, modules, businesses, locale }: { initial?: Initial; verticals: Option[]; modules: Option[]; businesses: Option[]; locale: Lang }) {
  const t = useTranslations("platform.broadcasts");
  const toast = useToast();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [id, setId] = useState<string | null>(initial?.id ?? null);
  const [kind, setKind] = useState<Kind>(initial?.kind ?? "service");
  const [channels, setChannels] = useState<Channel[]>(initial?.channels ?? ["email"]);
  const [audience, setAudience] = useState<Audience>(
    initial?.audience ?? { groups: [], verticals: [], locales: [], business_ids: [], modules: [], status: null },
  );
  const [content, setContent] = useState<Record<Lang, Texts>>({
    he: { ...BLANK, ...initial?.content?.he },
    en: { ...BLANK, ...initial?.content?.en },
  });
  const [sendNow, setSendNow] = useState(true);
  const [at, setAt] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | undefined>();

  const body = useMemo<BroadcastBody>(
    () => ({ kind, channels, audience, content: { he: content.he, en: content.en } }),
    [kind, channels, audience, content],
  );
  const audienceKey = JSON.stringify([kind, audience]);

  useEffect(() => {
    if (audience.groups.length === 0) return;
    let stale = false;
    const timer = setTimeout(() => {
      previewAudience(kind, audience).then((result) => {
        if (!stale) setPreview(result);
      });
    }, 300);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- audienceKey stands for kind and audience
  }, [audienceKey]);

  const shown = audience.groups.length === 0 ? null : preview;
  const update = (patch: Partial<Audience>) => setAudience((a) => ({ ...a, ...patch }));
  const setText = (lang: Lang, field: keyof Texts, value: string) => setContent((c) => ({ ...c, [lang]: { ...c[lang], [field]: value } }));
  const editable = !initial || initial.status === "draft" || initial.status === "scheduled";

  const run = (work: () => Promise<BroadcastResult>, done: (result: BroadcastResult) => void) => {
    setError(undefined);
    startTransition(async () => {
      const result = await work();
      if (result.id) setId(result.id);
      if (result.error) {
        setError(t(`errors.${result.error as "generic"}`));
        return;
      }
      done(result);
    });
  };

  const applyTemplate = (name: string) => {
    if (!name) return;
    const key = name as (typeof TEMPLATES)[number];
    setContent((c) => ({ ...c, [locale]: { ...c[locale], subject: t(`templates.${key}.subject`), body: t(`templates.${key}.body`) } }));
    setKind(key === "promo" || key === "feature" ? "marketing" : "service");
  };

  const submitTime = sendNow || !at ? null : new Date(at).toISOString();
  const count = shown?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      {error && <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}

      <fieldset className="flex flex-col gap-2" disabled={!editable}>
        <legend className="text-sm font-medium">{t("kind")}</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {(["service", "marketing"] as const).map((value) => (
            <label key={value} className={`flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 text-sm ${kind === value ? "border-primary bg-primary/10" : "border-border"}`}>
              <span className="flex items-center gap-2 font-semibold">
                <input type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="accent-[var(--primary)]" />
                {t(`kinds.${value}`)}
              </span>
              <span className="text-xs text-muted">{t(`kindHints.${value}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <Checks legend={t("channelsTitle")} items={CHANNELS.map((c) => ({ value: c, label: t(`channels.${c}`), hint: t(`channelHints.${c}`) }))} selected={channels} onChange={setChannels} />

      <section className="flex flex-col gap-4 rounded-2xl border border-border p-4" aria-labelledby="audience-title">
        <h2 id="audience-title" className="font-semibold">
          {t("audienceTitle")}
        </h2>
        <Checks legend={t("audienceTitle")} items={GROUPS.map((g) => ({ value: g, label: t(`groups.${g}`) }))} selected={audience.groups} onChange={(groups) => update({ groups })} />
        <details className="rounded-xl border border-border p-3" open={Boolean(audience.status || audience.verticals.length || audience.locales.length || audience.modules.length || audience.business_ids.length)}>
          <summary className="cursor-pointer text-sm font-medium">{t("filters.title")}</summary>
          <div className="mt-3 flex flex-col gap-4">
            <p className="text-xs text-muted">{t("filters.hint")}</p>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="b-status" className="text-sm font-medium">
                {t("filters.status")}
              </label>
              <select id="b-status" className="control px-3 py-2" value={audience.status ?? ""} onChange={(e) => update({ status: (e.target.value || null) as Audience["status"] })}>
                <option value="">{t("filters.any")}</option>
                <option value="trial">{t("filters.trial")}</option>
                <option value="active">{t("filters.active")}</option>
              </select>
            </div>
            <Checks legend={t("filters.locales")} items={LANGS.map((l) => ({ value: l, label: t(`content.language.${l}`) }))} selected={audience.locales} onChange={(locales) => update({ locales })} />
            <Checks legend={t("filters.verticals")} items={verticals.map((v) => ({ value: v.value, label: v.label }))} selected={audience.verticals} onChange={(next) => update({ verticals: next })} />
            <Checks legend={t("filters.modules")} items={modules.map((m) => ({ value: m.value, label: m.label }))} selected={audience.modules} onChange={(next) => update({ modules: next })} />
            <Checks legend={t("filters.businesses")} items={businesses.map((b) => ({ value: b.value, label: b.label }))} selected={audience.business_ids} onChange={(next) => update({ business_ids: next })} />
          </div>
        </details>
        <div aria-live="polite" className="rounded-xl bg-primary/10 px-4 py-3 text-sm">
          <p className="font-semibold">
            {t("preview.title")}: {shown ? t("preview.total", { count: shown.total }) : "..."}
          </p>
          {shown && shown.total === 0 && <p className="text-muted">{t("preview.none")}</p>}
          {shown && shown.total > 0 && (
            <>
              <p className="text-muted">
                {Object.entries(shown.by_group)
                  .map(([group, people]) => `${t(`groups.${group as Group}`)}: ${people}`)
                  .join(" · ")}
              </p>
              <p className="text-muted">
                {t("channels.email")}: {shown.email} · {t("channels.push")}: {shown.push} · {t("channels.popup")}: {shown.popup} · {t("preview.phone")}: {shown.phone}
              </p>
              <p className="text-xs text-muted">{t("preview.note")}</p>
            </>
          )}
          {kind === "marketing" && <p className="mt-1 text-xs text-muted">{t("preview.marketingNote")}</p>}
        </div>
      </section>

      <section className="flex flex-col gap-4 rounded-2xl border border-border p-4" aria-labelledby="content-title">
        <h2 id="content-title" className="font-semibold">
          {t("content.title")}
        </h2>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="b-template" className="text-sm font-medium">
            {t("templates.label")}
          </label>
          <select id="b-template" className="control px-3 py-2" value="" onChange={(e) => applyTemplate(e.target.value)}>
            <option value="">{t("templates.none")}</option>
            {TEMPLATES.map((name) => (
              <option key={name} value={name}>
                {t(`templates.${name}.name`)}
              </option>
            ))}
          </select>
        </div>
        <p className="text-xs text-muted">{t("content.fallback")}</p>
        {LANGS.map((lang) => (
          <fieldset key={lang} className="flex flex-col gap-3 rounded-xl border border-border p-3" lang={lang} dir={lang === "he" ? "rtl" : "ltr"}>
            <legend className="px-1 text-sm font-semibold">{t(`content.language.${lang}`)}</legend>
            <input aria-label={`${t("content.subject")} (${t(`content.language.${lang}`)})`} placeholder={t("content.subject")} maxLength={150} value={content[lang].subject} onChange={(e) => setText(lang, "subject", e.target.value)} className="control w-full px-3 py-2" />
            <textarea aria-label={`${t("content.body")} (${t(`content.language.${lang}`)})`} placeholder={t("content.body")} maxLength={4000} rows={5} value={content[lang].body} onChange={(e) => setText(lang, "body", e.target.value)} className="control w-full px-3 py-2" />
            <div className="grid gap-3 sm:grid-cols-2">
              <input aria-label={`${t("content.ctaLabel")} (${t(`content.language.${lang}`)})`} placeholder={t("content.ctaLabel")} maxLength={60} value={content[lang].cta_label} onChange={(e) => setText(lang, "cta_label", e.target.value)} className="control w-full px-3 py-2" />
              <input aria-label={`${t("content.ctaUrl")} (${t(`content.language.${lang}`)})`} placeholder={t("content.ctaUrl")} dir="ltr" type="url" maxLength={500} value={content[lang].cta_url} onChange={(e) => setText(lang, "cta_url", e.target.value)} className="control w-full px-3 py-2" />
            </div>
            <input aria-label={`${t("content.imageUrl")} (${t(`content.language.${lang}`)})`} placeholder={t("content.imageUrl")} dir="ltr" type="url" maxLength={500} value={content[lang].image_url} onChange={(e) => setText(lang, "image_url", e.target.value)} className="control w-full px-3 py-2" />
          </fieldset>
        ))}
      </section>

      {editable && (
        <>
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">{t("when.title")}</legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="when" checked={sendNow} onChange={() => setSendNow(true)} className="accent-[var(--primary)]" />
              {t("when.now")}
            </label>
            <label className="flex flex-wrap items-center gap-2 text-sm">
              <input type="radio" name="when" checked={!sendNow} onChange={() => setSendNow(false)} className="accent-[var(--primary)]" />
              {t("when.later")}
              <input type="datetime-local" aria-label={t("when.later")} value={at} disabled={sendNow} onChange={(e) => setAt(e.target.value)} className="control px-3 py-1.5" dir="ltr" />
            </label>
          </fieldset>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={pending}
              className="btn-primary px-4 py-2.5"
              onClick={() => {
                if (!window.confirm(t("actions.confirm", { count }))) return;
                run(() => scheduleBroadcast(id, body, submitTime), () => {
                  toast("success", t("notices.scheduled"));
                  router.push("/platform/broadcasts");
                });
              }}
            >
              {sendNow ? t("actions.send") : t("actions.schedule")}
            </button>
            <button type="button" disabled={pending} className="btn-secondary px-4 py-2.5" onClick={() => run(() => saveBroadcast(id, body), (r) => {
              toast("success", t("notices.saved"));
              if (!initial && r.id) router.replace(`/platform/broadcasts/${r.id}`);
            })}>
              {t("actions.saveDraft")}
            </button>
            <button type="button" disabled={pending} className="btn-secondary px-4 py-2.5" onClick={() => run(() => sendTest(id, body), (r) => toast(r.tested ? "success" : "error", r.tested ? t("notices.testSent", { email: r.testedTo ?? "" }) : t("notices.testNoProvider")))}>
              {t("actions.test")}
            </button>
            {id && (
              <>
                <button type="button" disabled={pending} className="btn-secondary px-4 py-2.5" onClick={() => run(() => cancelBroadcast(id), () => {
                  toast("success", t("notices.cancelled"));
                  router.push("/platform/broadcasts");
                })}>
                  {t("actions.cancel")}
                </button>
                <button type="button" disabled={pending} className="btn-danger px-4 py-2.5" onClick={() => run(() => deleteBroadcast(id), () => {
                  toast("success", t("notices.deleted"));
                  router.push("/platform/broadcasts");
                })}>
                  {t("actions.delete")}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
