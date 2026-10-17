import { FileText } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { acceptLegal } from "@/app/(app)/legal-actions";
import { SubmitButton } from "@/components/form/submit-button";

type Pending = { document: string; version: string };

/** Asks the person to accept the legal documents they have not accepted in their current
 * version (new ones, or ones that changed). Shows nothing when everything is accepted. */
export async function LegalBanner({ pending }: { pending: Pending[] }) {
  if (pending.length === 0) return null;
  const t = await getTranslations("legalUpdate");
  const documents = Object.fromEntries(pending.map((item) => [item.document, item.version]));
  return (
    <form action={acceptLegal} role="status" className="flex flex-wrap items-center justify-center gap-3 border-b border-border bg-primary/10 px-4 py-2 text-sm">
      <FileText aria-hidden="true" className="size-4" />
      <span>{t("text")}</span>
      <span className="flex flex-wrap gap-x-3">
        {pending.map((item) => (
          <Link key={item.document} href={`/legal/${item.document}`} target="_blank" className="font-medium underline underline-offset-4">
            {t(`documents.${item.document as "terms" | "privacy" | "dpa"}`)}
          </Link>
        ))}
      </span>
      <input type="hidden" name="documents" value={JSON.stringify(documents)} />
      <SubmitButton className="px-3 py-1.5">{t("accept")}</SubmitButton>
    </form>
  );
}
