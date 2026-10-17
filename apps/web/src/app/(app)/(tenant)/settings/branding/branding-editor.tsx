"use client";

import { AlertTriangle, Check, Image as ImageIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useState } from "react";

import { CheckboxField, Field } from "@/components/form/field";
import { FileField } from "@/components/form/file-field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { ImageCropDialog } from "@/components/image-crop-dialog";
import { SegmentedControl } from "@/components/segmented-control";
import { ContentSwap } from "@/components/ui/content-swap";
import { brandStyle, checkBrandColor, DEFAULT_BRAND_COLOR } from "@/lib/brand";
import { BRAND_PRESETS } from "@/lib/brand-presets";

import { type BrandingState, saveBranding } from "../actions";

type Tab = "app" | "receipt" | "join";

/** Branding in two columns: the settings on one side, "how it looks" on the other, updated as you
 * type. One Save for everything (name, color, logo, cover). */
export function BrandingEditor({ name, color, logo, cover }: { name: string; color: string | null; logo: string | null; cover: string | null }) {
  const t = useTranslations("settings");
  const tBranding = useTranslations("settings.branding");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<BrandingState, FormData>(saveBranding, {});

  const [displayName, setDisplayName] = useState(name);
  const [chosen, setChosen] = useState(color ?? DEFAULT_BRAND_COLOR);
  const [useDefault, setUseDefault] = useState(color === null);
  const [tab, setTab] = useState<Tab>("app");

  // The logo is cropped to a square first; what is saved is the crop.
  const [cropping, setCropping] = useState<File | null>(null);
  const [newLogo, setNewLogo] = useState<{ file: File; url: string } | null>(null);
  const [newCover, setNewCover] = useState<{ file: File; url: string } | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [removeCover, setRemoveCover] = useState(false);
  // Free the temporary preview addresses when they are replaced or the page closes.
  useEffect(() => () => { if (newLogo) URL.revokeObjectURL(newLogo.url); }, [newLogo]);
  useEffect(() => () => { if (newCover) URL.revokeObjectURL(newCover.url); }, [newCover]);

  const activeColor = useDefault ? null : chosen;
  const check = checkBrandColor(chosen);
  const logoSrc = newLogo?.url ?? (removeLogo ? null : logo);
  const coverSrc = newCover?.url ?? (removeCover ? null : cover);

  const error = state.error
    ? state.error === "logo_too_large" || state.error === "unsupported_image"
      ? t(`errors.${state.error}`)
      : state.error === "cover_too_large"
        ? t("coverTooLarge")
        : tCommon(`errors.${state.error}`)
    : undefined;

  return (
    <form
      action={async (data) => {
        // The cropped logo replaces the file that was picked.
        if (newLogo) data.set("logo", newLogo.file);
        else data.delete("logo");
        if (newCover) data.set("cover", newCover.file);
        else data.delete("cover");
        await action(data);
      }}
      className="grid gap-6 xl:grid-cols-2 xl:items-start"
    >
      <FormError message={error} toastOnly />
      <FormNotice message={state.saved ? tCommon("saved") : undefined} />

      <div className="flex flex-col gap-6">
        <section aria-labelledby="branding-name" className="card flex flex-col gap-4 p-5">
          <h3 id="branding-name" className="font-semibold">{tBranding("nameTitle")}</h3>
          <Field label={tBranding("name")} name="name" required maxLength={120} value={displayName} onChange={(event) => setDisplayName(event.target.value)} hint={tBranding("nameHint")} />
        </section>

        <section aria-labelledby="branding-color" className="card flex flex-col gap-4 p-5">
          <h3 id="branding-color" className="font-semibold">{t("color")}</h3>
          <div role="radiogroup" aria-label={tBranding("presetsLabel")} className="flex flex-wrap gap-2.5">
            {BRAND_PRESETS.map((preset) => {
              const selected = !useDefault && chosen === preset.color;
              return (
                <button
                  key={preset.key}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-label={tBranding(`presets.${preset.key}`)}
                  title={tBranding(`presets.${preset.key}`)}
                  onClick={() => {
                    setChosen(preset.color);
                    setUseDefault(false);
                  }}
                  style={{ backgroundColor: preset.color }}
                  className="btn-plain grid size-10 place-items-center rounded-full ring-offset-2 ring-offset-surface transition-shadow aria-checked:ring-2 aria-checked:ring-foreground"
                >
                  {selected && <Check aria-hidden="true" className="size-5 text-white drop-shadow" />}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-end gap-6">
            <Field
              label={tBranding("custom")}
              name="primary_color"
              type="color"
              value={chosen}
              disabled={useDefault}
              onChange={(event) => setChosen(event.target.value)}
              className="control h-11 w-20 cursor-pointer p-1"
            />
            <CheckboxField label={t("useDefault")} name="use_default" checked={useDefault} onChange={(event) => setUseDefault(event.target.checked)} />
          </div>
          {!useDefault && (
            <p
              role="status"
              className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm ${
                check.level === "good" ? "border-success/40 bg-success/10" : "border-warning/50 bg-warning/10"
              }`}
            >
              {check.level === "good" ? (
                <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              ) : (
                <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              )}
              <span>{tBranding(`check.${check.level}`)}</span>
            </p>
          )}
        </section>

        <section aria-labelledby="branding-logo" className="card flex flex-col gap-4 p-5">
          <h3 id="branding-logo" className="font-semibold">{t("logo")}</h3>
          <FileField
            label={t("uploadLogo")}
            hint={t("logoHint")}
            name="logo"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              setNewLogo(null);
              setCropping(event.target.files?.[0] ?? null);
            }}
          />
          {logo && !newLogo && (
            <CheckboxField label={t("removeLogo")} name="remove_logo" checked={removeLogo} onChange={(event) => setRemoveLogo(event.target.checked)} />
          )}
        </section>

        <section aria-labelledby="branding-cover" className="card flex flex-col gap-4 p-5">
          <h3 id="branding-cover" className="font-semibold">{t("cover")}</h3>
          <FileField
            label={t("uploadCover")}
            hint={t("coverHint")}
            name="cover"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              const file = event.target.files?.[0];
              setNewCover(file ? { file, url: URL.createObjectURL(file) } : null);
            }}
          />
          {cover && !newCover && (
            <CheckboxField label={t("removeCover")} name="remove_cover" checked={removeCover} onChange={(event) => setRemoveCover(event.target.checked)} />
          )}
        </section>

        <div>
          <SubmitButton>{tCommon("save")}</SubmitButton>
        </div>
      </div>

      <section aria-labelledby="branding-preview" className="card order-first flex flex-col gap-4 p-5 xl:sticky xl:top-24 xl:order-none">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 id="branding-preview" className="font-semibold">{tBranding("preview.title")}</h3>
          <SegmentedControl
            label={tBranding("preview.title")}
            value={tab}
            onChange={setTab}
            options={(["app", "receipt", "join"] as const).map((value) => ({ value, label: tBranding(`preview.tabs.${value}`) }))}
          />
        </div>
        <div style={brandStyle(activeColor)} className="brand rounded-2xl border border-border bg-background p-4">
          <ContentSwap swapKey={tab}>
            {tab === "app" && <AppPreview name={displayName} logo={logoSrc} cover={coverSrc} />}
            {tab === "receipt" && <ReceiptPreview name={displayName} logo={logoSrc} />}
            {tab === "join" && <JoinPreview name={displayName} logo={logoSrc} />}
          </ContentSwap>
        </div>
      </section>

      {cropping && (
        <ImageCropDialog
          file={cropping}
          onCancel={() => setCropping(null)}
          onDone={(file) => {
            setCropping(null);
            setRemoveLogo(false);
            setNewLogo({ file, url: URL.createObjectURL(file) });
          }}
        />
      )}
    </form>
  );
}

/** The logo, or the first letter of the name on the brand color. */
function Mark({ name, logo, size }: { name: string; logo: string | null; size: "sm" | "lg" }) {
  const t = useTranslations("settings");
  const box = size === "lg" ? "size-16 text-2xl" : "size-11 text-lg";
  if (logo) {
    // eslint-disable-next-line @next/next/no-img-element -- a private or local preview image
    return <img src={logo} alt={t("logoPreview")} className={`${box} shrink-0 rounded-xl border border-border bg-background object-contain`} />;
  }
  return (
    <span aria-hidden="true" className={`${box} grid shrink-0 place-items-center rounded-xl bg-primary font-bold text-on-primary`}>
      {name.trim().slice(0, 1).toUpperCase() || <ImageIcon className="size-5" />}
    </span>
  );
}

function AppPreview({ name, logo, cover }: { name: string; logo: string | null; cover: string | null }) {
  const t = useTranslations("settings");
  const tp = useTranslations("settings.branding.preview");
  return (
    <div className="mx-auto flex max-w-sm flex-col overflow-hidden rounded-2xl border border-border bg-surface">
      {cover ? (
        // eslint-disable-next-line @next/next/no-img-element -- a private or local preview image
        <img src={cover} alt="" className="aspect-[3/1] w-full object-cover" />
      ) : (
        <div aria-hidden="true" className="aspect-[3/1] w-full bg-primary/15" />
      )}
      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-center gap-3">
          <Mark name={name} logo={logo} size="sm" />
          <div className="min-w-0">
            <p className="truncate font-semibold" dir="auto">{name || "-"}</p>
            <p className="text-sm text-muted">{tp("greeting")}</p>
          </div>
        </div>
        <div className="flex flex-col gap-2 rounded-xl border border-border p-3">
          <p className="text-sm text-muted">{tp("next")}</p>
          <p className="font-medium">{tp("nextItem")}</p>
          <span className="btn-primary self-start px-4 py-2 text-sm">{t("previewButton")}</span>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="rounded-full bg-primary px-3 py-1 text-on-primary">{tp("chipOne")}</span>
          <span className="rounded-full bg-primary/10 px-3 py-1 font-medium text-primary-ink">{tp("chipTwo")}</span>
          <span className="rounded-full border border-border px-3 py-1">{tp("chipThree")}</span>
        </div>
      </div>
    </div>
  );
}

function ReceiptPreview({ name, logo }: { name: string; logo: string | null }) {
  const tp = useTranslations("settings.branding.preview");
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 overflow-hidden rounded-2xl border border-border bg-surface">
      <div aria-hidden="true" className="h-2 bg-primary" />
      <div className="flex flex-col gap-4 p-5">
        <div className="flex items-center gap-3">
          <Mark name={name} logo={logo} size="sm" />
          <p className="min-w-0 truncate font-semibold" dir="auto">{name || "-"}</p>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-lg font-bold text-primary-ink">{tp("receipt")}</p>
          <p className="text-sm text-muted tabular-nums">{tp("receiptNumber")}</p>
        </div>
        <ul className="flex flex-col divide-y divide-border text-sm">
          <li className="flex justify-between gap-3 py-2"><span>{tp("receiptItem")}</span><bdi className="tabular-nums">120.00</bdi></li>
          <li className="flex justify-between gap-3 py-2"><span>{tp("receiptVat")}</span><bdi className="tabular-nums">20.40</bdi></li>
        </ul>
        <p className="flex justify-between gap-3 border-t border-border pt-3 font-bold"><span>{tp("receiptTotal")}</span><bdi className="tabular-nums">140.40</bdi></p>
      </div>
    </div>
  );
}

function JoinPreview({ name, logo }: { name: string; logo: string | null }) {
  const tp = useTranslations("settings.branding.preview");
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center gap-4 rounded-2xl border border-border bg-surface p-6 text-center">
      <Mark name={name} logo={logo} size="lg" />
      <p className="text-xl font-bold text-balance" dir="auto">{tp("joinTitle", { name: name || "-" })}</p>
      <p className="text-sm text-muted">{tp("joinHint")}</p>
      <span className="btn-primary w-full justify-center px-4 py-2.5">{tp("joinButton")}</span>
    </div>
  );
}
