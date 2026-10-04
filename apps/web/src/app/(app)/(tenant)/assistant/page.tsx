import type { components } from "@business-os/api-client";
import { FlaskConical } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canUseAssistant } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { askAssistant, decideAction, newConversation } from "./actions";
import { AskForm } from "./ask-form";

type PendingAction = components["schemas"]["PendingAction"];

const STATUS_TONE: Record<PendingAction["status"], string> = {
  pending: "text-primary",
  executed: "text-success",
  rejected: "text-muted",
  expired: "text-muted",
  failed: "text-danger",
};

async function ActionCard({ action }: { action: PendingAction }) {
  const t = await getTranslations("assistant");
  const preview = action.preview as { kind: string; client: string; service: string; starts: string; full?: boolean };
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-primary/40 bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("needsConfirmation")}</p>
      <p className="font-medium" dir="auto">
        {preview.kind === "cancel_booking"
          ? t("cancelPreview", { client: preview.client, service: preview.service })
          : t("bookPreview", { client: preview.client, service: preview.service })}
        {" · "}
        <span dir="ltr">{preview.starts}</span>
      </p>
      {preview.full && <p className="text-sm text-muted">{t("fullWaitlist")}</p>}
      {action.status === "pending" ? (
        <div className="flex gap-2">
          <form action={decideAction.bind(null, action.id, "confirm")}>
            <button type="submit" className="btn-primary px-3 py-1.5 text-sm">
              {t("confirm")}
            </button>
          </form>
          <form action={decideAction.bind(null, action.id, "reject")}>
            <button type="submit" className="btn-secondary px-3 py-1.5 text-sm font-medium">
              {t("reject")}
            </button>
          </form>
        </div>
      ) : (
        <p role="status" className={`text-sm font-medium ${STATUS_TONE[action.status]}`}>
          {t(`statuses.${action.status}`)}
        </p>
      )}
    </div>
  );
}

export default async function AssistantPage({ searchParams }: PageProps<"/assistant">) {
  const t = await getTranslations("assistant");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canUseAssistant(tenant) || !tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")) {
    redirect("/dashboard");
  }
  const query = await searchParams;
  const requested = typeof query.c === "string" ? query.c : null;

  const [status, conversations] = await Promise.all([
    api.GET("/ai/status", { params: scope }).then(unwrap),
    api.GET("/ai/conversations", { params: scope }).then(unwrap),
  ]);
  const conversationId = requested ?? conversations[0]?.id ?? null;
  const conversation = conversationId
    ? (await api.GET("/ai/conversations/{conversation_id}", { params: { ...scope, path: { conversation_id: conversationId } } })).data
    : null;
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short", timeZone: tenant.time_zone });

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
        <form action={newConversation}>
          <button type="submit" className="btn-secondary px-4 py-2.5">
            {t("newConversation")}
          </button>
        </form>
      </div>

      {status.demo && (
        <p role="note" className="flex items-start gap-2 rounded-2xl border border-warning/50 bg-warning/10 p-4 text-sm">
          <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {t("demoMode")}
        </p>
      )}

      {!status.enabled && (
        <p role="status" className="rounded-2xl border border-dashed border-border p-6 text-muted">
          {t("notConfigured")}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
        <section aria-label={t("conversation")} className="flex min-h-96 flex-col gap-4 card p-5">
          {!conversation ? (
            <p className="text-muted">{t("empty")}</p>
          ) : (
            <>
              <ol className="flex flex-1 flex-col gap-4">
                {conversation.turns.length === 0 && <li className="text-muted">{t("intro")}</li>}
                {conversation.turns.map((turn, index) => (
                  <li key={index} className={`flex flex-col gap-2 ${turn.role === "user" ? "items-end" : "items-start"}`}>
                    <span className="sr-only">{turn.role === "user" ? t("you") : t("assistantLabel")}</span>
                    {turn.role === "user" ? (
                      <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-on-primary" dir="auto">
                        {turn.text}
                      </p>
                    ) : (
                      <div className="flex max-w-[85%] flex-col gap-3">
                        <p className="whitespace-pre-wrap rounded-2xl bg-background px-4 py-2.5" dir="auto">
                          {turn.text || t("noAnswer")}
                        </p>
                        {turn.pending_actions.map((action) => (
                          <ActionCard key={action.id} action={action} />
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
              {status.enabled && (
                <AskForm
                  key={conversation.turns.length}
                  action={askAssistant.bind(null, conversation.id)}
                  suggestions={conversation.turns.length === 0 ? [t("suggestion1"), t("suggestion2"), t("suggestion3")] : []}
                />
              )}
            </>
          )}
          {!conversation && status.enabled && (
            <form action={newConversation}>
              <button type="submit" className="btn-primary px-4 py-2.5">
                {t("start")}
              </button>
            </form>
          )}
        </section>

        {conversations.length > 0 && (
          <nav aria-label={t("history")} className="flex flex-col gap-1">
            <h2 className="px-2 text-sm font-semibold text-muted">{t("history")}</h2>
            {conversations.map((item) => (
              <Link
                key={item.id}
                href={`/assistant?c=${item.id}`}
                aria-current={item.id === conversationId ? "page" : undefined}
                className={`flex flex-col rounded-lg px-2 py-1.5 text-sm hover:bg-surface ${item.id === conversationId ? "bg-surface font-medium" : ""}`}
              >
                <span className="truncate" dir="auto">
                  {item.title || t("untitled")}
                </span>
                <span className="text-xs text-muted">{when.format(new Date(item.updated_at))}</span>
              </Link>
            ))}
          </nav>
        )}
      </div>
    </main>
  );
}
