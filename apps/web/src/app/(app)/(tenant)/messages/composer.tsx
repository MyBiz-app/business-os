"use client";

import type { components } from "@business-os/api-client";
import { CheckCheck, MessageCircle, Send, Smartphone } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useRef, useState } from "react";

import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type SendState, sendCampaign } from "./actions";

type AudienceCount = components["schemas"]["AudienceCount"];
type Template = components["schemas"]["Template"];

const VARIABLES = ["first_name", "business"] as const;

type Props = {
  audiences: AudienceCount[];
  templates: Template[];
  suggestions: { name: string; body: string }[];
  businessName: string;
  sampleName: string;
};

/** Write a message, pick who gets it, and see it as they will. */
export function Composer({ audiences, templates, suggestions, businessName, sampleName }: Props) {
  const t = useTranslations("messaging");
  const [state, action] = useActionState<SendState, FormData>(sendCampaign, {});
  const [audience, setAudience] = useState(audiences[0]?.audience ?? "active");
  const [channel, setChannel] = useState<"whatsapp" | "sms">("whatsapp");
  const [body, setBody] = useState("");
  const textArea = useRef<HTMLTextAreaElement>(null);
  const count = audiences.find((a) => a.audience === audience)?.recipients ?? 0;
  const preview = body.replaceAll("{first_name}", sampleName).replaceAll("{business}", businessName);

  const insert = (variable: string) => {
    const element = textArea.current;
    const token = `{${variable}}`;
    if (!element) return setBody((value) => value + token);
    const start = element.selectionStart;
    const next = body.slice(0, start) + token + body.slice(element.selectionEnd);
    setBody(next);
    requestAnimationFrame(() => {
      element.focus();
      element.setSelectionRange(start + token.length, start + token.length);
    });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <form action={action} className="flex flex-col gap-4">
        <FormError message={state.error && t("errors.generic")} />
        {state.sent !== undefined && (
          <p role="status" className="flex items-center gap-2 rounded-xl border border-success/40 bg-success/10 px-4 py-2 text-sm font-medium">
            <CheckCheck aria-hidden="true" className="size-4" />
            {t("sentTo", { count: state.sent })}
          </p>
        )}
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("audience")}
          <select
            name="audience"
            value={audience}
            onChange={(event) => setAudience(event.target.value as typeof audience)}
            className="control px-3 py-2 font-normal"
          >
            {audiences.map((a) => (
              <option key={a.audience} value={a.audience}>
                {t(`audiences.${a.audience}`)} ({a.recipients})
              </option>
            ))}
          </select>
        </label>

        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1.5 text-sm font-medium">{t("channel")}</legend>
          <div className="flex gap-2">
            {(["whatsapp", "sms"] as const).map((value) => (
              <label
                key={value}
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${
                  channel === value ? "border-primary bg-primary/10" : "border-border bg-surface hover:border-primary/50"
                }`}
              >
                <input
                  type="radio"
                  name="channel"
                  value={value}
                  checked={channel === value}
                  onChange={() => setChannel(value)}
                  className="sr-only"
                />
                {value === "whatsapp" ? <MessageCircle aria-hidden="true" className="size-4" /> : <Smartphone aria-hidden="true" className="size-4" />}
                {t(`channels.${value}`)}
              </label>
            ))}
          </div>
        </fieldset>

        {(templates.length > 0 || suggestions.length > 0) && (
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            {t("startFrom")}
            <select
              value=""
              onChange={(event) => {
                if (event.target.value) setBody(event.target.value);
              }}
              className="control px-3 py-2 font-normal"
            >
              <option value="">{t("chooseTemplate")}</option>
              {templates.length > 0 && (
                <optgroup label={t("myTemplates")}>
                  {templates.map((template) => (
                    <option key={template.id} value={template.body}>
                      {template.name}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label={t("suggested")}>
                {suggestions.map((suggestion) => (
                  <option key={suggestion.name} value={suggestion.body}>
                    {suggestion.name}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="message-body" className="text-sm font-medium">
            {t("text")}
          </label>
          <textarea
            id="message-body"
            ref={textArea}
            name="body"
            required
            maxLength={1000}
            rows={6}
            dir="auto"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            aria-describedby="message-help"
            className="control w-full px-3 py-2"
          />
          <div id="message-help" className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>{t("insert")}</span>
            {VARIABLES.map((variable) => (
              <button
                key={variable}
                type="button"
                onClick={() => insert(variable)}
                className="rounded-full bg-primary/10 px-2.5 py-1 font-medium text-foreground transition-colors hover:bg-primary/20"
              >
                {t(`variables.${variable}`)}
              </button>
            ))}
            <span className="ms-auto tabular-nums">{body.length}/1000</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <SubmitButton>
            <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
            {t("sendTo", { count })}
          </SubmitButton>
          <span className="text-xs text-muted">{t("simulatedHint")}</span>
        </div>
      </form>

      <figure aria-label={t("preview")} className="mx-auto w-full max-w-xs">
        <div className="overflow-hidden rounded-[2rem] border-8 border-zinc-900 bg-[#efe7dd] shadow-xl dark:border-zinc-700 dark:bg-[#0b141a]">
          <div className="flex items-center gap-2 bg-[#075e54] px-4 py-3 text-sm font-semibold text-white">
            <span aria-hidden="true" className="flex size-7 items-center justify-center rounded-full bg-white/20">
              {businessName.slice(0, 1)}
            </span>
            {businessName}
          </div>
          <div className="flex min-h-72 flex-col justify-end gap-2 p-3">
            {preview ? (
              <p
                dir="auto"
                className="max-w-[85%] self-end whitespace-pre-wrap rounded-xl rounded-se-sm bg-[#d9fdd3] px-3 py-2 text-sm text-zinc-900 shadow-sm dark:bg-[#005c4b] dark:text-zinc-50"
              >
                {preview}
              </p>
            ) : (
              <p className="self-center rounded-lg bg-white/70 px-3 py-1 text-xs text-zinc-700 dark:bg-black/40 dark:text-zinc-200">
                {t("previewEmpty")}
              </p>
            )}
          </div>
        </div>
        <figcaption className="mt-2 text-center text-xs text-muted">{t("previewCaption", { name: sampleName })}</figcaption>
      </figure>
    </div>
  );
}
