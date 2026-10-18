"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Tour, type TourStep } from "@/components/tour/tour";

import { AgentAvatar } from "./agent-avatar";
import type { Agent } from "./types";

/** The first guide of the AI team. The conversation in it is written in advance: it never calls the
 * model, so it costs no credits, and "Confirm" in it only shows what would happen. */
export function AiTour({ agents, canManage, onClose }: { agents: Agent[]; canManage: boolean; onClose: () => void }) {
  const t = useTranslations("aiTeam.tour");
  const faces = agents.filter((a) => a.state === "active").slice(0, 6);
  const asker = agents.find((a) => a.key === "secretary" && a.state === "active") ?? faces[0] ?? agents[0];

  const steps: TourStep[] = [
    {
      id: "team",
      title: t("team.title"),
      body: (
        <>
          <p>{t("team.body")}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {faces.map((agent) => (
              <li key={agent.key} className="flex items-center gap-3 rounded-xl border border-border p-2">
                <AgentAvatar agent={agent} className="size-10 shrink-0" />
                <span className="flex min-w-0 flex-col leading-tight">
                  <span className="truncate font-semibold" dir="auto">
                    {agent.name}
                  </span>
                  <span className="truncate text-xs text-muted" dir="auto">
                    {agent.role_title}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
    { id: "talk", title: t("talk.title"), body: <p>{t("talk.body")}</p> },
    {
      id: "approvals",
      title: t("approvals.title"),
      body: (
        <>
          <p>{t("approvals.body")}</p>
          {asker && <Simulation agent={asker} />}
        </>
      ),
    },
    { id: "usage", title: t("usage.title"), body: <p>{t("usage.body")}</p> },
    { id: "hire", title: t("hire.title"), body: <p>{canManage ? t("hire.body") : t("hire.bodyMember")}</p> },
    { id: "map", target: "ai-map", title: t("spots.map.title"), body: <p>{t("spots.map.body")}</p> },
    { id: "toolbar", target: "ai-toolbar", title: t("spots.toolbar.title"), body: <p>{t("spots.toolbar.body")}</p> },
    { id: "meter", target: "ai-usage", title: t("spots.meter.title"), body: <p>{t("spots.meter.body")}</p> },
  ];
  return <Tour steps={steps} onClose={onClose} />;
}

/** A short recorded chat: a question, an answer, and a card that waits for the owner's decision. */
function Simulation({ agent }: { agent: Agent }) {
  const t = useTranslations("aiTeam.tour.simulation");
  const tAssistant = useTranslations("assistant");
  const [decision, setDecision] = useState<"confirm" | "reject" | null>(null);
  return (
    <section aria-label={t("label")} className="flex flex-col gap-3 rounded-2xl border border-dashed border-border bg-surface p-3">
      <p className="self-end rounded-2xl bg-primary px-3 py-2 text-on-primary">{t("question")}</p>
      <div className="flex items-start gap-2">
        <AgentAvatar agent={agent} className="size-8 shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <p className="rounded-2xl border border-border bg-background px-3 py-2" dir="auto">
            {t("answer", { name: agent.name })}
          </p>
          <div className="flex flex-col gap-2 rounded-xl border border-primary/40 bg-background p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">{tAssistant("needsConfirmation")}</p>
            <p className="font-medium">{t("card")}</p>
            {decision ? (
              <p role="status" className="text-sm text-muted">
                {t(decision === "confirm" ? "confirmed" : "rejected")}
              </p>
            ) : (
              <div className="flex gap-2">
                <button type="button" onClick={() => setDecision("confirm")} className="btn-primary px-3 py-1.5 text-sm">
                  {tAssistant("confirm")}
                </button>
                <button type="button" onClick={() => setDecision("reject")} className="btn-secondary px-3 py-1.5 text-sm font-medium">
                  {tAssistant("reject")}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
