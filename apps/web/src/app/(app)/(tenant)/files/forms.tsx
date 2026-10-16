"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { Field } from "@/components/form/field";
import { FileField } from "@/components/form/file-field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { createFolder, uploadFile } from "./actions";

export function UploadForm({ folderId }: { folderId: string }) {
  const t = useTranslations("files");
  const [state, action] = useActionState(uploadFile.bind(null, folderId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <FileField label={t("file")} hint={t("fileHint")} name="file" required accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt" />
      <Field label={t("name")} name="name" maxLength={200} dir="auto" />
      <div>
        <SubmitButton>{t("upload")}</SubmitButton>
      </div>
    </form>
  );
}

export function NewFolderForm({ parentId }: { parentId: string | null }) {
  const t = useTranslations("files");
  const [state, action] = useActionState(createFolder.bind(null, parentId), {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <Field label={t("folderName")} name="name" required maxLength={120} dir="auto" />
      <div>
        <SubmitButton>{t("createFolder")}</SubmitButton>
      </div>
    </form>
  );
}
