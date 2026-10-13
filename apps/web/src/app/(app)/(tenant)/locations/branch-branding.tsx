"use client";

import type { components } from "@business-os/api-client";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { useActionState, useState } from "react";

import { CheckboxField, Field } from "@/components/form/field";
import { FileField } from "@/components/form/file-field";
import { FormFeedback } from "@/components/form/form-feedback";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { ImageCropDialog } from "@/components/image-crop-dialog";
import { brandStyle } from "@/lib/brand";
import type { FormState } from "@/lib/form-state";

import { type BrandingState, removeBranchLogo, updateBranchColor, uploadBranchLogo } from "./actions";

type Location = components["schemas"]["Location"];

const FALLBACK_COLOR = "#2563eb";

/** A branch's own logo and color; without them it shows the network's (the business's). */
export function BranchBranding({ location, logo, networkColor }: { location: Location; logo: string | null; networkColor: string | null }) {
  const t = useTranslations("locations");
  const tSettings = useTranslations("settings");
  const tCommon = useTranslations("common");
  const [logoState, logoAction] = useActionState<BrandingState, FormData>(uploadBranchLogo.bind(null, location.id), {});
  const [colorState, colorAction] = useActionState<FormState, FormData>(updateBranchColor.bind(null, location.id), {});
  const [cropping, setCropping] = useState<File | null>(null);
  const [cropped, setCropped] = useState<{ file: File; url: string } | null>(null);
  const [useNetwork, setUseNetwork] = useState(location.primary_color === null);
  const [preview, setPreview] = useState(location.primary_color ?? networkColor ?? FALLBACK_COLOR);
  const logoError =
    logoState.error === "logo_too_large" || logoState.error === "unsupported_image"
      ? tSettings(`errors.${logoState.error}`)
      : logoState.error && tCommon("errors.generic");

  return (
    <section aria-labelledby="branding-heading" className="flex flex-col gap-6 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="branding-heading" className="text-lg font-semibold">
          {t("brandingTitle")}
        </h2>
        <p className="text-sm text-muted">{t("brandingHint")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="font-semibold">{t("logo")}</h3>
        <div className="flex flex-wrap items-center gap-4">
          {logo ? (
            <Image src={logo} alt="" width={64} height={64} unoptimized className="size-16 rounded-xl border border-border bg-background object-contain" />
          ) : (
            <span className="text-sm text-muted">{t("logoNetwork")}</span>
          )}
          {logo && (
            <form action={removeBranchLogo.bind(null, location.id)}>
              <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                {t("logoRemove")}
              </button>
            </form>
          )}
        </div>
        <form
          key={location.logo_url ?? "none"}
          action={async (data) => {
            if (cropped) data.set("logo", cropped.file);
            await logoAction(data);
          }}
          className="flex flex-col gap-3"
        >
          <FormError message={logoError} />
          <FormNotice message={logoState.saved ? tCommon("saved") : undefined} />
          <FileField
            label={t("logo")}
            hint={t("logoHint")}
            name="logo"
            accept="image/png,image/jpeg,image/webp"
            required
            onChange={(event) => {
              setCropped(null);
              setCropping(event.target.files?.[0] ?? null);
            }}
          />
          {cropped && (
            // eslint-disable-next-line @next/next/no-img-element -- a local preview of the cropped logo
            <img src={cropped.url} alt={tSettings("logoPreview")} className="size-20 rounded-full object-cover ring-1 ring-border" />
          )}
          <div>
            <SubmitButton>{t("logoUpload")}</SubmitButton>
          </div>
        </form>
        {cropping && (
          <ImageCropDialog
            file={cropping}
            onCancel={() => setCropping(null)}
            onDone={(file) => {
              setCropping(null);
              setCropped({ file, url: URL.createObjectURL(file) });
            }}
          />
        )}
      </div>

      <form action={colorAction} className="flex flex-col gap-4 border-t border-border pt-6">
        <FormFeedback state={colorState} />
        <div className="flex flex-wrap items-end gap-6">
          <Field
            label={t("color")}
            name="primary_color"
            type="color"
            value={preview}
            disabled={useNetwork}
            onChange={(event) => setPreview(event.target.value)}
            className="control h-11 w-20 cursor-pointer p-1"
          />
          <CheckboxField label={t("colorNetwork")} name="use_network" checked={useNetwork} onChange={(event) => setUseNetwork(event.target.checked)} />
        </div>
        <div style={brandStyle(useNetwork ? networkColor : preview)} className="brand flex items-center gap-3">
          <span className="btn-primary px-4 py-2.5">{tSettings("previewButton")}</span>
        </div>
        <div>
          <SubmitButton>{tCommon("save")}</SubmitButton>
        </div>
      </form>
    </section>
  );
}
