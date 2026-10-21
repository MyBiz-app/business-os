"use client";

import { ArrowLeft, ArrowRight, ImagePlus, Send, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { type ReactNode, useRef, useState, useTransition } from "react";

import { ChoiceCard } from "@/components/form/choice-card";
import { Field, TextAreaField } from "@/components/form/field";
import { useToast } from "@/components/toast/toaster";

import { saveBrief, submitBrief, uploadSiteImage } from "../actions";
import type { Draft } from "./draft";
import { Button, IconButton, buttonClass } from "@/components/ui/button";

type Brief = Draft;

const STEPS = ["goal", "business", "sections", "branding", "motion", "images", "inspiration", "domain"] as const;
const GOALS = ["leads", "bookings", "showcase", "sell"] as const;
const SECTIONS = ["hero", "services", "gallery", "team", "testimonials", "faq", "location", "contact", "booking", "whatsapp"] as const;
const STYLES = ["clean", "luxury", "warm", "vibrant"] as const;
const MOTIONS = ["none", "subtle", "rich"] as const;
const DOMAINS = ["have", "buy", "temporary"] as const;
const LANGUAGES = ["he", "en"] as const;

type Props = {
  initial: Brief;
  folderId: string;
  withSystem: boolean;
  brandColor: string;
  /** The names of images already uploaded, by file id (the draft only keeps ids). */
  fileNames: Record<string, string>;
};

function toggle<T extends string>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function Group({ legend, children }: { legend: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

/** "Tell us about your website": eight short steps, saved as a draft after each one, then one
 * summary to send. Opens in a large window over the page it was started from. */
export function WebsiteWizard({ initial, folderId, withSystem, brandColor, fileNames }: Props) {
  const t = useTranslations("website");
  const toast = useToast();
  const router = useRouter();
  const [brief, setBrief] = useState<Brief>(initial);
  const [step, setStep] = useState(0);
  const [names, setNames] = useState(fileNames);
  const [missing, setMissing] = useState<string[]>([]);
  const [busy, startSaving] = useTransition();
  const [uploading, setUploading] = useState(false);
  const upload = useRef<HTMLInputElement>(null);
  const logo = useRef<HTMLInputElement>(null);
  const last = step === STEPS.length;
  const set = (changes: Partial<Brief>) => setBrief((current) => ({ ...current, ...changes }));

  function fail(error: "locked" | "invalid" | "generic") {
    toast("error", t(`errors.${error}`));
  }

  function go(to: number) {
    startSaving(async () => {
      const result = await saveBrief(brief);
      if (!result.ok) return fail(result.error);
      setMissing(result.missing);
      setStep(to);
    });
  }

  function send() {
    startSaving(async () => {
      const saved = await saveBrief(brief);
      if (!saved.ok) return fail(saved.error);
      const result = await submitBrief();
      if (!result.ok) return fail(result.error);
      toast("success", t("sent"));
      router.replace("/website");
    });
  }

  async function addImages(files: FileList | null, as: "image" | "logo") {
    if (!files?.length) return;
    setUploading(true);
    const added: Brief["images"] = [];
    let logoId: string | null = null;
    for (const file of Array.from(files).slice(0, as === "logo" ? 1 : 20 - brief.images.length)) {
      const body = new FormData();
      body.set("file", file);
      const result = await uploadSiteImage(folderId, body);
      if (!result.ok) {
        toast("error", t(`errors.${result.error}`));
        continue;
      }
      setNames((current) => ({ ...current, [result.fileId]: result.name }));
      if (as === "logo") logoId = result.fileId;
      else added.push({ file_id: result.fileId, note: null });
    }
    setUploading(false);
    if (as === "logo" && logoId) set({ logo_file_id: logoId, no_logo: false });
    if (added.length) set({ images: [...brief.images, ...added] });
    if (upload.current) upload.current.value = "";
    if (logo.current) logo.current.value = "";
  }

  const colors = brief.colors.length ? brief.colors : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-medium text-muted" aria-live="polite">
          {last ? t("summaryStep") : t("stepOf", { current: step + 1, total: STEPS.length })}
        </p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface" aria-hidden="true">
          <div className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none" style={{ width: `${((step + (last ? 0 : 1)) / STEPS.length) * 100}%` }} />
        </div>
      </div>

      {!last && <h3 className="text-lg font-semibold">{t(`steps.${STEPS[step]}.title`)}</h3>}
      {!last && <p className="-mt-4 text-sm text-muted">{t(`steps.${STEPS[step]}.hint`)}</p>}

      {step === 0 && (
        <div className="flex flex-col gap-4">
          <Group legend={t("steps.goal.goals")}>
            {GOALS.map((goal) => (
              <ChoiceCard key={goal} type="checkbox" title={t(`goals.${goal}`)} checked={brief.goals.includes(goal)} onChange={() => set({ goals: toggle(brief.goals, goal) })} />
            ))}
          </Group>
          <Field label={t("steps.goal.mainAction")} hint={t("steps.goal.mainActionHint")} maxLength={200} value={brief.main_action ?? ""} onChange={(event) => set({ main_action: event.target.value })} />
        </div>
      )}

      {step === 1 && (
        <div className="flex flex-col gap-4">
          <TextAreaField label={t("steps.business.unique")} maxLength={1200} rows={4} value={brief.unique ?? ""} onChange={(event) => set({ unique: event.target.value })} />
          <Field label={t("steps.business.audience")} maxLength={200} value={brief.audience ?? ""} onChange={(event) => set({ audience: event.target.value })} />
          <Field label={t("steps.business.area")} maxLength={200} value={brief.area ?? ""} onChange={(event) => set({ area: event.target.value })} />
        </div>
      )}

      {step === 2 && (
        <Group legend={t("steps.sections.legend")}>
          {SECTIONS.map((section) => (
            <ChoiceCard
              key={section}
              type="checkbox"
              title={t(`sections.${section}.title`)}
              hint={section === "booking" && !withSystem ? t("sections.booking.needsSystem") : t(`sections.${section}.hint`)}
              disabled={section === "booking" && !withSystem}
              checked={brief.sections.includes(section)}
              onChange={() => set({ sections: toggle(brief.sections, section) })}
            />
          ))}
        </Group>
      )}

      {step === 3 && (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">{t("steps.branding.logo")}</p>
            <div className="flex flex-wrap items-center gap-3">
              <input ref={logo} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" id="site-logo" onChange={(event) => addImages(event.target.files, "logo")} />
              <label htmlFor="site-logo" className={buttonClass("secondary", "md", "cursor-pointer")}>
                <ImagePlus aria-hidden="true" className="size-4" />
                {brief.logo_file_id ? t("steps.branding.replaceLogo") : t("steps.branding.uploadLogo")}
              </label>
              {brief.logo_file_id && <span className="text-sm text-muted" dir="auto">{names[brief.logo_file_id] ?? ""}</span>}
            </div>
            <ChoiceCard type="checkbox" title={t("steps.branding.noLogo")} checked={brief.no_logo} onChange={(event) => set({ no_logo: event.target.checked, logo_file_id: event.target.checked ? null : brief.logo_file_id })} />
          </div>
          <div className="flex flex-col gap-2">
            <ChoiceCard type="checkbox" title={t("steps.branding.fromBrand")} checked={brief.colors_from_brand} onChange={(event) => set({ colors_from_brand: event.target.checked })} />
            {!brief.colors_from_brand && (
              <div className="flex flex-wrap items-center gap-3">
                {(colors.length ? colors : [brandColor]).map((color, index) => (
                  <input
                    key={index}
                    type="color"
                    aria-label={t("steps.branding.color", { number: index + 1 })}
                    className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-surface"
                    value={color}
                    onChange={(event) => set({ colors: Object.assign([...(colors.length ? colors : [brandColor])], { [index]: event.target.value }) })}
                  />
                ))}
                {(colors.length ? colors : [brandColor]).length < 4 && (
                  <Button variant="secondary" onClick={() => set({ colors: [...(colors.length ? colors : [brandColor]), brandColor] })}>
                    {t("steps.branding.addColor")}
                  </Button>
                )}
              </div>
            )}
          </div>
          <Group legend={t("steps.branding.style")}>
            {STYLES.map((style) => (
              <ChoiceCard key={style} type="radio" name="style" title={t(`styles.${style}.title`)} hint={t(`styles.${style}.hint`)} checked={brief.style === style} onChange={() => set({ style })} />
            ))}
          </Group>
          <Field label={t("steps.branding.font")} hint={t("steps.branding.fontHint")} maxLength={200} value={brief.font ?? ""} onChange={(event) => set({ font: event.target.value })} />
        </div>
      )}

      {step === 4 && (
        <Group legend={t("steps.motion.legend")}>
          {MOTIONS.map((motion) => (
            <ChoiceCard key={motion} type="radio" name="motion" title={t(`motions.${motion}.title`)} hint={t(`motions.${motion}.hint`)} checked={brief.motion === motion} onChange={() => set({ motion })} />
          ))}
        </Group>
      )}

      {step === 5 && (
        <div className="flex flex-col gap-4">
          <input ref={upload} type="file" multiple accept="image/png,image/jpeg,image/webp" className="sr-only" id="site-images" onChange={(event) => addImages(event.target.files, "image")} />
          <label htmlFor="site-images" aria-disabled={uploading || brief.images.length >= 20} className={buttonClass("secondary", "md", "w-fit cursor-pointer")}>
            <ImagePlus aria-hidden="true" className="size-4" />
            {uploading ? t("steps.images.uploading") : t("steps.images.upload")}
          </label>
          <ul className="flex flex-col gap-3">
            {brief.images.map((image, index) => (
              <li key={image.file_id} className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface p-3">
                <span className="min-w-0 flex-1 truncate text-sm" dir="auto">{names[image.file_id] ?? ""}</span>
                <div className="w-full sm:w-72">
                  <Field label={t("steps.images.note")} maxLength={200} value={image.note ?? ""} onChange={(event) => set({ images: brief.images.map((item, i) => (i === index ? { ...item, note: event.target.value } : item)) })} />
                </div>
                <IconButton variant="secondary" label={t("steps.images.remove")} onClick={() => set({ images: brief.images.filter((_, i) => i !== index) })}>
                  <X aria-hidden="true" className="size-4" />
                </IconButton>
              </li>
            ))}
          </ul>
          <ChoiceCard type="checkbox" title={t("steps.images.noGood")} hint={t("steps.images.noGoodHint")} checked={brief.no_good_photos} onChange={(event) => set({ no_good_photos: event.target.checked })} />
        </div>
      )}

      {step === 6 && (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-3">
            <p className="text-sm font-medium">{t("steps.inspiration.sites")}</p>
            {[0, 1, 2].map((index) => {
              const site = brief.inspiration[index];
              const update = (changes: Partial<{ url: string; likes: string }>) => {
                const next = [0, 1, 2].map((i) => (i === index ? { url: site?.url ?? "", likes: site?.likes ?? "", ...changes } : (brief.inspiration[i] ?? { url: "", likes: "" })));
                set({ inspiration: next.filter((item) => item.url.trim() !== "").map((item) => ({ url: item.url.trim(), likes: item.likes || null })) });
              };
              return (
                <div key={index} className="grid gap-3 sm:grid-cols-2">
                  <Field label={t("steps.inspiration.url", { number: index + 1 })} type="url" dir="ltr" placeholder="https://" value={site?.url ?? ""} onChange={(event) => update({ url: event.target.value })} />
                  <Field label={t("steps.inspiration.likes")} maxLength={200} value={site?.likes ?? ""} disabled={!site} onChange={(event) => update({ likes: event.target.value })} />
                </div>
              );
            })}
          </div>
          <Group legend={t("steps.inspiration.copy")}>
            {(["me", "you"] as const).map((who) => (
              <ChoiceCard key={who} type="radio" name="copy_by" title={t(`copyBy.${who}`)} checked={brief.copy_by === who} onChange={() => set({ copy_by: who })} />
            ))}
          </Group>
        </div>
      )}

      {step === 7 && (
        <div className="flex flex-col gap-5">
          <Group legend={t("steps.domain.legend")}>
            {DOMAINS.map((domain) => (
              <ChoiceCard key={domain} type="radio" name="domain" title={t(`domains.${domain}.title`)} hint={t(`domains.${domain}.hint`)} checked={brief.domain === domain} onChange={() => set({ domain })} />
            ))}
          </Group>
          {brief.domain === "have" && <Field label={t("steps.domain.name")} dir="ltr" maxLength={200} value={brief.domain_name ?? ""} onChange={(event) => set({ domain_name: event.target.value })} />}
          <Group legend={t("steps.domain.languages")}>
            {LANGUAGES.map((language) => (
              <ChoiceCard key={language} type="checkbox" title={t(`languages.${language}`)} checked={brief.languages.includes(language)} onChange={() => set({ languages: toggle(brief.languages, language) })} />
            ))}
          </Group>
          <Field label={t("steps.domain.dueDate")} type="date" value={brief.due_date ?? ""} onChange={(event) => set({ due_date: event.target.value || null })} />
        </div>
      )}

      {last && (
        <div className="flex flex-col gap-4">
          <h3 className="text-lg font-semibold">{t("summary.title")}</h3>
          <p className="text-sm text-muted">{t("summary.hint")}</p>
          <dl className="grid gap-3 rounded-xl border border-border bg-surface p-4 text-sm sm:grid-cols-2">
            <div><dt className="text-muted">{t("steps.goal.goals")}</dt><dd>{brief.goals.map((g) => t(`goals.${g}`)).join(", ") || "-"}</dd></div>
            <div><dt className="text-muted">{t("steps.sections.legend")}</dt><dd>{brief.sections.map((s) => t(`sections.${s}.title`)).join(", ") || "-"}</dd></div>
            <div><dt className="text-muted">{t("steps.branding.style")}</dt><dd>{brief.style ? t(`styles.${brief.style}.title`) : "-"}</dd></div>
            <div><dt className="text-muted">{t("steps.motion.legend")}</dt><dd>{brief.motion ? t(`motions.${brief.motion}.title`) : "-"}</dd></div>
            <div><dt className="text-muted">{t("steps.domain.legend")}</dt><dd>{brief.domain ? t(`domains.${brief.domain}.title`) : "-"}</dd></div>
            <div><dt className="text-muted">{t("steps.domain.languages")}</dt><dd>{brief.languages.map((l) => t(`languages.${l}`)).join(", ") || "-"}</dd></div>
          </dl>
          {missing.length > 0 && (
            <div role="alert" className="rounded-xl border border-warning/50 bg-warning/10 p-3 text-sm">
              <p className="font-medium">{t("summary.missing")}</p>
              <ul className="mt-1 list-disc ps-5">
                {missing.map((key) => (
                  <li key={key}>{t(`missing.${key as "goals"}`)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <Button variant="secondary" disabled={busy || step === 0} onClick={() => go(step - 1)}>
          <ArrowLeft aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          {t("back")}
        </Button>
        <span className="text-xs text-muted">{t("autosave")}</span>
        {last ? (
          <Button variant="primary" disabled={busy || missing.length > 0} onClick={send}>
            <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
            {t("send")}
          </Button>
        ) : (
          <Button variant="primary" disabled={busy || uploading} onClick={() => go(step + 1)}>
            {step === STEPS.length - 1 ? t("toSummary") : t("next")}
            <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          </Button>
        )}
      </div>
    </div>
  );
}
