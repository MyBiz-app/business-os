"use client";

import type { components } from "@business-os/api-client";
import { Bell, Mail, MessageCircle, MessageSquare, Send, Smartphone } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useRef, useState } from "react";

import { BranchScopePicker, type ScopeBranch, type ScopeGroup } from "@/components/branch-scope-picker";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type Reach, type SendState, previewCampaign, sendCampaign } from "./actions";
import { VariablePicker, type VariableGroup, type VariableName } from "./variable-picker";
import { isolate } from "@/lib/bidi";

type AudienceCount = components["schemas"]["AudienceCount"];
type Template = components["schemas"]["Template"];

const PHONE = ["whatsapp", "sms"] as const;
const NET = ["email", "push", "popup"] as const;
type ChannelKey = (typeof PHONE)[number] | (typeof NET)[number];
const ICONS = { whatsapp: MessageCircle, sms: Smartphone, email: Mail, push: Bell, popup: MessageSquare };

type Props = {
  audiences: AudienceCount[];
  templates: Template[];
  suggestions: { name: string; body: string }[];
  businessName: string;
  /** A made-up client's values, for the live preview. */
  sample: Record<string, string>;
  variableGroups: VariableGroup[];
  /** The branches this person may message (a single one hides the picker). */
  branches: ScopeBranch[];
  groups: ScopeGroup[];
};

/** Write a message, pick who gets it, and see it as they will. */
export function Composer({ audiences, templates, suggestions, businessName, sample, variableGroups, branches, groups }: Props) {
  const t = useTranslations("messaging");
  const [state, action] = useActionState<SendState, FormData>(sendCampaign, {});
  const [audience, setAudience] = useState(audiences[0]?.audience ?? "active");
  const [channels, setChannels] = useState<ChannelKey[]>(["whatsapp"]);
  const [scope, setScope] = useState<string[]>(branches.map((branch) => branch.id));
  const [promotional, setPromotional] = useState(false);
  const [body, setBody] = useState("");
  const textArea = useRef<HTMLTextAreaElement>(null);
  const staff = audience === "staff";
  const allBranches = scope.length === branches.length;
  const usable = staff ? channels.filter((c) => (NET as readonly string[]).includes(c)) : channels;
  const needsSubject = usable.some((c) => (NET as readonly string[]).includes(c));
  const [reach, setReach] = useState<Reach>(() => ({
    recipients: audiences.find((a) => a.audience === audience)?.recipients ?? 0,
    byChannel: audiences.find((a) => a.audience === audience)?.by_channel ?? {},
    warnings: [],
  }));
  const nobody = usable.length === 0 || scope.length === 0;
  const count = nobody ? 0 : reach.recipients;

  // The live count follows who, which branches and which channels.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (usable.length === 0 || scope.length === 0) return;
    let current = true;
    const timer = setTimeout(() => {
      previewCampaign({ audience, channels: usable, locationIds: allBranches ? null : scope, promotional }).then(
        (result) => current && setReach(result),
      );
    }, 250);
    return () => {
      current = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audience, usable.join(","), scope.join(","), promotional]);

  const toggleChannel = (value: ChannelKey) =>
    setChannels((current) => (current.includes(value) ? current.filter((c) => c !== value) : [...current, value]));
  const sampleName = sample.first_name ?? "";
  const preview = body.replace(/\{([a-z0-9_]+)(?:\|([^{}]*))?\}/g, (whole, name: string, fallback?: string) =>
    name in sample ? sample[name] || (fallback ?? "").trim() : whole,
  );
  const [missing, setMissing] = useState<{ variable: string; recipients: number }[]>([]);
  const shownMissing = body.includes("{") && !nobody ? missing : [];

  // Variables some recipients have no value for, checked on the server as the text is written.
  useEffect(() => {
    if (!body.includes("{") || usable.length === 0 || scope.length === 0) return;
    let current = true;
    const timer = setTimeout(() => {
      previewCampaign({ audience, channels: usable, locationIds: allBranches ? null : scope, promotional, body }).then(
        (result) => current && setMissing(result.warnings),
      );
    }, 500);
    return () => {
      current = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [body, audience, usable.join(","), scope.join(","), promotional]);

  const insert = (token: string) => {
    const element = textArea.current;
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
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem] xl:grid-cols-1 2xl:grid-cols-[1fr_20rem]">
      <form action={action} className="flex flex-col gap-4">
        <FormError message={state.error && t("errors.generic")} />
        <FormNotice message={state.sent !== undefined ? t("sentTo", { count: state.sent }) : undefined} />
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
                {t(`audiences.${a.audience}`)}
              </option>
            ))}
          </select>
        </label>

        {branches.length > 1 && audience !== "open_leads" && (
          <>
            <BranchScopePicker branches={branches} groups={groups} value={scope} onChange={setScope} legend={t("branches")} />
            {!allBranches && scope.map((id) => <input key={id} type="hidden" name="location_ids" value={id} />)}
          </>
        )}

        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1.5 text-sm font-medium">{t("channel")}</legend>
          <div className="flex flex-wrap gap-2">
            {[...PHONE, ...NET].map((value) => {
              const Icon = ICONS[value];
              const blocked = staff && (PHONE as readonly string[]).includes(value);
              const on = channels.includes(value) && !blocked;
              return (
                <label
                  key={value}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${
                    blocked ? "cursor-not-allowed opacity-50" : "cursor-pointer"
                  } ${on ? "border-primary bg-primary/10" : "border-border bg-surface hover:border-primary/50"}`}
                >
                  <input
                    type="checkbox"
                    name="channels"
                    value={value}
                    checked={on}
                    disabled={blocked}
                    onChange={() => toggleChannel(value)}
                    className="sr-only"
                  />
                  <Icon aria-hidden="true" className="size-4" />
                  {t(`channels.${value}`)}
                  {on && reach.byChannel[value] !== undefined && (
                    <span className="text-xs font-normal tabular-nums text-muted">{reach.byChannel[value]}</span>
                  )}
                </label>
              );
            })}
          </div>
          <p className="text-xs text-muted">{staff ? t("staffChannelsHint") : t("channelsHint")}</p>
        </fieldset>

        {needsSubject && (
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            {t("subject")}
            <input name="subject" maxLength={150} dir="auto" placeholder={businessName} className="control px-3 py-2 font-normal" />
          </label>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="promotional"
            checked={promotional}
            onChange={(event) => setPromotional(event.target.checked)}
          />
          <span>
            {t("promotional")} <span className="text-xs text-muted">{t("promotionalHint")}</span>
          </span>
        </label>

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
                        <VariablePicker groups={variableGroups} onPick={insert} />
            <span className="ms-auto tabular-nums">{body.length}/1000</span>
          </div>
          {shownMissing.length > 0 && (
            <ul role="status" className="flex flex-col gap-1 rounded-lg border border-warning/50 bg-warning/10 px-3 py-2 text-xs">
              {shownMissing.map((item) => (
                <li key={item.variable}>
                  {t("missingValue", { count: item.recipients, variable: t(`variables.${item.variable as VariableName}`) })}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <SubmitButton disabled={count === 0}>
            <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
            {t("sendTo", { count })}
          </SubmitButton>
          <span className="text-xs text-muted">{t("simulatedHint")}</span>
        </div>
      </form>

      <figure aria-label={t("preview")} className={`mx-auto w-full max-w-xs ${preview ? "" : "max-lg:hidden"}`}>
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
        <figcaption className="mt-2 text-center text-xs text-muted">{t("previewCaption", { name: isolate(sampleName) })}</figcaption>
      </figure>
    </div>
  );
}
