"use client";

import { ArrowLeft, History, Plus, SendHorizontal, Settings } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { isolate } from "@/lib/bidi";
import { formatMoney } from "@/lib/money";

import type { ChatError, Conversation, ConversationSummary } from "./actions";
import { AgentAvatar } from "./agent-avatar";
import { type Branch, ScopePicker } from "./scope-picker";
import type { Agent } from "./types";

type PendingAction = Conversation["turns"][number]["pending_actions"][number];

const STATUS_TONE: Record<PendingAction["status"], string> = {
  pending: "text-primary",
  executed: "text-success",
  rejected: "text-muted",
  expired: "text-muted",
  failed: "text-danger",
};

export function ActionCard({ action, onDecide }: { action: PendingAction; onDecide: (id: string, decision: "confirm" | "reject") => void }) {
  const t = useTranslations("assistant");
  const locale = useLocale();
  const preview = action.preview as {
    kind: string;
    client?: string;
    service?: string;
    starts?: string;
    full?: boolean;
    dependent?: string;
    date?: string;
    hours?: number;
    description?: string;
    month?: string;
    clients?: number;
    names?: string[];
    total?: number;
    currency?: string;
  };
  const month = (value: string) => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}-15T12:00:00Z`));
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-primary/40 bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("needsConfirmation")}</p>
      {preview.kind === "log_time" ? (
        <p className="font-medium" dir="auto">
          {t("logTimePreview", { hours: new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(preview.hours ?? 0), client: isolate(preview.client ?? ""), description: isolate(preview.description ?? "") })}
          {" · "}
          <span dir="ltr">{preview.date}</span>
        </p>
      ) : preview.kind === "bill_month" ? (
        <>
          <p className="font-medium" dir="auto">
            {t("billMonthPreview", { count: preview.clients ?? 0, month: month(preview.month ?? ""), total: formatMoney(preview.total ?? 0, preview.currency ?? "ILS", locale) })}
          </p>
          {preview.names && preview.names.length > 0 && (
            <p className="text-sm text-muted" dir="auto">
              {preview.names.map((name) => isolate(name)).join(", ")}
              {(preview.clients ?? 0) > preview.names.length ? "…" : ""}
            </p>
          )}
        </>
      ) : (
        <p className="font-medium" dir="auto">
          {preview.kind === "cancel_booking"
            ? t("cancelPreview", { client: isolate(preview.client ?? ""), service: isolate(preview.service ?? "") })
            : t("bookPreview", { client: isolate(preview.dependent ? `${preview.dependent} (${preview.client})` : (preview.client ?? "")), service: isolate(preview.service ?? "") })}
          {" · "}
          <span dir="ltr">{preview.starts}</span>
        </p>
      )}
      {preview.full && <p className="text-sm text-muted">{t("fullWaitlist")}</p>}
      {action.status === "pending" ? (
        <div className="flex gap-2">
          <button type="button" onClick={() => onDecide(action.id, "confirm")} className="btn-primary px-3 py-1.5 text-sm">
            {t("confirm")}
          </button>
          <button type="button" onClick={() => onDecide(action.id, "reject")} className="btn-secondary px-3 py-1.5 text-sm font-medium">
            {t("reject")}
          </button>
        </div>
      ) : (
        <p role="status" className={`text-sm font-medium ${STATUS_TONE[action.status]}`}>
          {t(`statuses.${action.status}`)}
        </p>
      )}
    </div>
  );
}

type Props = {
  agent: Agent;
  agents: Agent[];
  conversation: Conversation | null;
  /** The question just sent, shown while the answer is on its way. */
  waitingFor: string | null;
  error: ChatError | null;
  enabled: boolean;
  branches: Branch[];
  scope: string[] | null;
  history: ConversationSummary[];
  timeZone: string;
  onScope: (ids: string[] | null) => void;
  onSend: (text: string) => void;
  onSwitch: (agent: Agent) => void;
  onNew: () => void;
  onOpen: (conversationId: string) => void;
  onHandoff: (agentKey: string) => void;
  onDecide: (actionId: string, decision: "confirm" | "reject") => void;
  onBack: () => void;
  /** Opens the agent's card for those who may change it. */
  onEdit?: () => void;
};

export function ChatPanel({ agent, agents, conversation, waitingFor, error, enabled, branches, scope, history, timeZone, onScope, onSend, onSwitch, onNew, onOpen, onHandoff, onDecide, onBack, onEdit }: Props) {
  const t = useTranslations("aiTeam");
  const tAssistant = useTranslations("assistant");
  const locale = useLocale();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const turns = conversation?.turns ?? [];
  const busy = waitingFor !== null;
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short", timeZone });
  const nameOf = (key: string) => agents.find((a) => a.key === key)?.name ?? key;
  const suggestions = turns.length === 0 && !busy ? (["s1", "s2", "s3"] as const).map((k) => t(`suggestions.${agent.builtin ? agent.key : "custom"}.${k}` as "suggestions.chief.s1")) : [];

  useEffect(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }), [turns.length, waitingFor]);

  function submit(value: string) {
    const question = value.trim();
    if (!question || busy || !enabled) return;
    setText("");
    onSend(question);
  }

  return (
    <section aria-label={t("chatWith", { name: agent.name })} className="ai-panel-in flex min-h-[32rem] min-w-0 flex-1 flex-col overflow-hidden rounded-3xl border border-border bg-surface">
      <header className="flex flex-wrap items-center gap-3 border-b border-border p-3 sm:p-4">
        <button type="button" onClick={onBack} className="btn-secondary p-2 lg:hidden" aria-label={t("backToTeam")}>
          <ArrowLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
        </button>
        <AgentAvatar agent={agent} className="size-12 shrink-0" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-semibold" dir="auto">
            {agent.name}
          </h2>
          <p className="truncate text-sm text-muted" dir="auto">
            {agent.role_title}
          </p>
        </div>
        <ScopePicker branches={branches} value={scope} onChange={onScope} />
        {onEdit && (
          <button type="button" onClick={onEdit} className="btn-secondary inline-flex items-center gap-2 px-3 py-1.5 text-sm">
            <Settings aria-hidden="true" className="size-4" />
            <span className="sr-only sm:not-sr-only">{t("edit.open")}</span>
          </button>
        )}
        <details className="relative">
          <summary className="btn-secondary inline-flex cursor-pointer list-none items-center gap-2 px-3 py-1.5 text-sm [&::-webkit-details-marker]:hidden">
            <History aria-hidden="true" className="size-4" />
            <span className="sr-only sm:not-sr-only">{t("history")}</span>
          </summary>
          <ul className="absolute end-0 z-30 mt-2 max-h-72 w-64 overflow-y-auto rounded-2xl border border-border bg-background p-2 shadow-lg" aria-label={t("history")}>
            {history.length === 0 && <li className="px-2 py-1.5 text-sm text-muted">{t("noHistory")}</li>}
            {history.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => onOpen(item.id)} aria-current={item.id === conversation?.id ? "true" : undefined} className={`flex w-full flex-col rounded-lg px-2 py-1.5 text-start text-sm hover:bg-surface ${item.id === conversation?.id ? "bg-surface font-medium" : ""}`}>
                  <span className="truncate" dir="auto">
                    {item.title || tAssistant("untitled")}
                  </span>
                  <span className="text-xs text-muted">{when.format(new Date(item.updated_at))}</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
        <button type="button" onClick={onNew} className="btn-secondary inline-flex items-center gap-2 px-3 py-1.5 text-sm">
          <Plus aria-hidden="true" className="size-4" />
          <span className="sr-only sm:not-sr-only">{t("newChat")}</span>
        </button>
      </header>

      <nav aria-label={t("switchAgent")} className="flex gap-2 overflow-x-auto border-b border-border px-3 py-2">
        {agents
          .filter((a) => a.state === "active")
          .map((other) => (
            <button
              key={other.key}
              type="button"
              onClick={() => onSwitch(other)}
              aria-current={other.key === agent.key ? "true" : undefined}
              aria-label={`${other.name}, ${other.role_title}`}
              title={`${other.name} · ${other.role_title}`}
              className={`shrink-0 rounded-full p-0.5 transition ${other.key === agent.key ? "" : "opacity-60 hover:opacity-100"}`}
              style={{ boxShadow: other.key === agent.key ? `0 0 0 2px ${other.color}` : undefined }}
            >
              <AgentAvatar agent={other} className="size-8" />
            </button>
          ))}
      </nav>

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-5" aria-live="polite">
        {turns.length === 0 && !busy && (
          <div className="m-auto flex max-w-md flex-col items-center gap-3 text-center">
            <AgentAvatar agent={agent} className="size-20" />
            <p className="text-lg font-semibold" dir="auto">
              {t("greeting", { name: agent.name })}
            </p>
            {agent.topic && (
              <p className="text-sm text-muted" dir="auto">
                {agent.topic}
              </p>
            )}
          </div>
        )}
        <ol className="mx-auto flex w-full max-w-3xl flex-col gap-4">
          {turns.map((turn, index) => (
            <li key={index} className={`flex flex-col gap-2 ${turn.role === "user" ? "items-end" : "items-start"}`}>
              <span className="sr-only">{turn.role === "user" ? tAssistant("you") : agent.name}</span>
              {turn.role === "user" ? (
                <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-on-primary" dir="auto">
                  {turn.text}
                </p>
              ) : (
                <div className="flex max-w-[85%] gap-2">
                  <AgentAvatar agent={agent} className="mt-1 size-7 shrink-0" />
                  <div className="flex min-w-0 flex-col gap-3">
                    <p className="whitespace-pre-wrap rounded-2xl bg-background px-4 py-2.5" dir="auto">
                      {turn.text || tAssistant("noAnswer")}
                    </p>
                    {turn.pending_actions.map((action) => (
                      <ActionCard key={action.id} action={action} onDecide={onDecide} />
                    ))}
                    {turn.suggestions.map((suggestion) => (
                      <button key={suggestion.agent_key} type="button" onClick={() => onHandoff(suggestion.agent_key)} className="flex flex-col items-start gap-1 rounded-xl border border-primary/40 bg-background p-3 text-start text-sm hover:bg-surface">
                        <span className="font-medium" dir="auto">
                          {t("handoff", { name: nameOf(suggestion.agent_key) })}
                        </span>
                        <span className="text-muted" dir="auto">
                          {suggestion.reason}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </li>
          ))}
          {waitingFor !== null && (
            <>
              {waitingFor && (
                <li className="flex justify-end">
                  <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-on-primary" dir="auto">
                    {waitingFor}
                  </p>
                </li>
              )}
              <li role="status" className="flex items-center gap-2 text-sm text-muted">
                <AgentAvatar agent={agent} className="size-7" />
                {t("thinking", { name: agent.name })}
              </li>
            </>
          )}
        </ol>
        <div ref={end} />
      </div>

      <div className="flex flex-col gap-3 border-t border-border p-3 sm:p-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {tAssistant(`errors.${error}`)}
          </p>
        )}
        {suggestions.length > 0 && enabled && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => submit(suggestion)} className="rounded-full border border-border bg-background px-3 py-1.5 text-sm hover:bg-surface" dir="auto">
                {suggestion}
              </button>
            ))}
          </div>
        )}
        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            submit(text);
          }}
        >
          <label className="sr-only" htmlFor="ai-question">
            {tAssistant("question")}
          </label>
          <textarea
            id="ai-question"
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit(text);
              }
            }}
            rows={2}
            maxLength={2000}
            disabled={!enabled}
            placeholder={t("placeholder", { name: agent.name })}
            className="min-h-[3rem] flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2"
            dir="auto"
          />
          <button type="submit" disabled={busy || !enabled || !text.trim()} className="btn-primary p-3 disabled:opacity-50" aria-label={tAssistant("send")}>
            <SendHorizontal aria-hidden="true" className="size-5 rtl:-scale-x-100" />
          </button>
        </form>
      </div>
    </section>
  );
}
