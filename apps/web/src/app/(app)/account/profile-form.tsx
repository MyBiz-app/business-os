"use client";

import { ImageUp, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { Field } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import type { FormState } from "@/lib/form-state";

import { type PictureState, removeAvatar, saveProfile, uploadAvatar } from "./actions";

export function ProfileForm({ name, email, phone }: { name: string | null; email: string; phone: string | null }) {
  const t = useTranslations();
  const [state, action] = useActionState<FormState, FormData>(saveProfile, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      <FormFeedback state={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("account.name")} hint={t("account.nameHint")} name="full_name" defaultValue={name ?? ""} maxLength={120} autoComplete="name" dir="auto" />
        <Field label={t("account.phone")} hint={t("account.phoneHint")} name="phone" type="tel" defaultValue={phone ?? ""} maxLength={30} autoComplete="tel" dir="ltr" pattern="[0-9+()\- ]*" />
      </div>
      <Field label={t("account.email")} hint={t("account.emailHint")} value={email} readOnly dir="ltr" />
      <div>
        <SubmitButton>{t("common.save")}</SubmitButton>
      </div>
    </form>
  );
}

/** The person's picture: pick a file to see it at once, then save it; or remove it. */
export function PictureForm({ id, name, src }: { id: string; name: string; src: string | null }) {
  const t = useTranslations("account");
  const tCommon = useTranslations("common");
  const [state, action] = useActionState<PictureState, FormData>(uploadAvatar, {});
  const [preview, setPreview] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const error = state.error === "generic" ? tCommon("errors.generic") : state.error && t(`pictureErrors.${state.error}`);

  return (
    <div className="flex flex-wrap items-center gap-5">
      <Avatar id={id} name={name} src={preview ?? src} size="xl" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <FormError message={error} />
        <FormNotice message={state.saved && !preview ? tCommon("saved") : undefined} />
        <form
          action={async (data) => {
            await action(data);
            setPreview(null);
          }}
          className="flex flex-wrap items-center gap-2"
        >
          <label className="btn-secondary cursor-pointer px-3 py-2 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary">
            <ImageUp aria-hidden="true" className="size-4" />
            {src ? t("replacePicture") : t("addPicture")}
            <input
              ref={input}
              type="file"
              name="avatar"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                setPreview(file ? URL.createObjectURL(file) : null);
              }}
            />
          </label>
          {preview && <SubmitButton className="px-3 py-2 text-sm">{t("savePicture")}</SubmitButton>}
        </form>
        {src && !preview && (
          <form action={removeAvatar}>
            <button type="submit" className="btn-ghost px-2 py-1 text-sm">
              <Trash2 aria-hidden="true" className="size-4" />
              {t("removePicture")}
            </button>
          </form>
        )}
        <p className="text-xs text-muted">{t("pictureHint")}</p>
      </div>
    </div>
  );
}
