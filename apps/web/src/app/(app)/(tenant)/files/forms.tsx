"use client";

import { useTranslations } from "next-intl";
import { Upload, FolderPlus } from "lucide-react";
import { useActionState, useEffect, useState } from "react";

import { Field } from "@/components/form/field";
import { FileField } from "@/components/form/file-field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import { Modal } from "@/components/ui/modal";

import { createFolder, uploadFile } from "./actions";

export function UploadForm({ folderId, onDone }: { folderId: string; onDone?: () => void }) {
  const t = useTranslations("files");
  const [state, action] = useActionState(uploadFile.bind(null, folderId), {});
  useEffect(() => {
    if (state.saved) onDone?.();
  }, [state.saved, onDone]);
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

export function NewFolderForm({ parentId, onDone }: { parentId: string | null; onDone?: () => void }) {
  const t = useTranslations("files");
  const [state, action] = useActionState(createFolder.bind(null, parentId), {});
  useEffect(() => {
    if (state.saved) onDone?.();
  }, [state.saved, onDone]);
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

/** The folder header's "Upload" and "New folder" buttons; each opens its form in a window. */
export function FolderActions({ folderId, canUpload, canCreateFolder }: { folderId: string; canUpload: boolean; canCreateFolder: boolean }) {
  const t = useTranslations("files");
  const [open, setOpen] = useState<"upload" | "folder" | null>(null);
  const close = () => setOpen(null);
  return (
    <>
      {canUpload && (
        <button type="button" onClick={() => setOpen("upload")} className="btn-primary px-3 py-1.5 text-sm">
          <Upload aria-hidden="true" className="size-4" /> {t("add")}
        </button>
      )}
      {canCreateFolder && (
        <button type="button" onClick={() => setOpen("folder")} className="btn-secondary px-3 py-1.5 text-sm">
          <FolderPlus aria-hidden="true" className="size-4" /> {t("newFolder")}
        </button>
      )}
      {open === "upload" && (
        <Modal title={t("add")} size="sm" onClose={close}>
          <UploadForm folderId={folderId} onDone={close} />
        </Modal>
      )}
      {open === "folder" && (
        <Modal title={t("newFolder")} size="sm" onClose={close}>
          <NewFolderForm parentId={folderId} onDone={close} />
        </Modal>
      )}
    </>
  );
}
