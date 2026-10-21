"use client";

import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Snippet = { key: "form" | "booking"; code: string };

/** The snippets a business with its own website pastes in: the contact form and a booking
 * button. Worth having without buying a MyBiz website. */
export function EmbedPanel({ contactUrl, bookingUrl, inquiriesEnabled }: { contactUrl: string; bookingUrl: string; inquiriesEnabled: boolean }) {
  const t = useTranslations("website.embed");
  const [copied, setCopied] = useState<string | null>(null);
  const snippets: Snippet[] = [
    ...(inquiriesEnabled
      ? [{ key: "form" as const, code: `<iframe src="${contactUrl}" title="${t("formTitle")}" width="100%" height="560" style="border:0" loading="lazy"></iframe>` }]
      : []),
    { key: "booking", code: `<a href="${bookingUrl}" style="display:inline-block;padding:12px 20px;border-radius:12px;background:black;color:white;font-family:sans-serif;text-decoration:none">${t("bookingLabel")}</a>` },
  ];
  return (
    <Card as="section" aria-labelledby="site-embed" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="site-embed" className="text-lg font-semibold">{t("title")}</h2>
        <p className="text-sm text-muted">{t("body")}</p>
      </div>
      {!inquiriesEnabled && <p className="rounded-xl border border-border bg-surface p-3 text-sm">{t("formOff")}</p>}
      {snippets.map(({ key, code }) => (
        <div key={key} className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{t(`${key}.title`)}</h3>
            <Button
              variant="secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(code).catch(() => undefined);
                setCopied(key);
                setTimeout(() => setCopied(null), 2000);
              }}
            >
              {copied === key ? <Check aria-hidden="true" className="size-4" /> : <Copy aria-hidden="true" className="size-4" />}
              <span aria-live="polite">{copied === key ? t("copied") : t("copy")}</span>
            </Button>
          </div>
          <p className="text-xs text-muted">{t(`${key}.hint`)}</p>
          <pre dir="ltr" className="control overflow-x-auto whitespace-pre-wrap break-all p-3 text-xs">{code}</pre>
        </div>
      ))}
    </Card>
  );
}
