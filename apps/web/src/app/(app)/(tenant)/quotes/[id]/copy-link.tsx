"use client";

import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

/** Copies the quote's private link to send it any way the business likes. */
export function CopyLink({ url }: { url: string }) {
  const t = useTranslations("quotes");
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(url).then(() => setCopied(true));
      }}
      className="btn-secondary px-3 py-2 text-sm"
    >
      {copied ? <Check aria-hidden="true" className="size-4" /> : <Copy aria-hidden="true" className="size-4" />}
      <span aria-live="polite">{copied ? t("copied") : t("copyLink")}</span>
    </button>
  );
}
