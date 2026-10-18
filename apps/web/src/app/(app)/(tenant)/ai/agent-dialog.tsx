"use client";

import { Check, Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { Modal } from "@/components/ui/modal";

import { AgentAvatar } from "./agent-avatar";
import type { Agent, Upsell } from "./types";

/** What a closed agent says when it's clicked: a locked one makes the case for its module (in full color), the others say why they can't be opened. */
export function AgentDialog({ agent, upsell, canAdd, onEdit, onClose }: { agent: Agent; upsell: Upsell | null; canAdd: boolean; onEdit?: () => void; onClose: () => void }) {
  const t = useTranslations("aiTeam");
  const locked = agent.state === "locked";
  return (
    <Modal
      title={locked ? t("upsell.title", { name: agent.name, role: agent.role_title }) : agent.name}
      size="sm"
      onClose={onClose}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="relative flex">
          <span aria-hidden="true" className="ai-halo absolute -inset-3 rounded-full blur-xl" style={{ backgroundColor: agent.color }} />
          <AgentAvatar agent={agent} className="relative size-28" />
          <span aria-hidden="true" className="absolute -bottom-1 end-0 grid size-8 place-items-center rounded-full border-2 border-background bg-surface">
            <Lock className="size-4" />
          </span>
        </span>
        {locked && agent.builtin ? (
          <>
            <p className="text-muted" dir="auto">
              {t(`upsell.pitch.${agent.key}` as "upsell.pitch.chief", { name: agent.name })}
            </p>
            <ul className="flex flex-col gap-2 text-start text-sm">
              {(["p1", "p2", "p3"] as const).map((point) => (
                <li key={point} className="flex items-start gap-2">
                  <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success-ink" />
                  {t(`upsell.${point}`)}
                </li>
              ))}
            </ul>
            {upsell && (
              <p className="text-sm text-muted">
                {t("upsell.price", { module: upsell.name, price: upsell.price })}
              </p>
            )}
            {canAdd ? (
              <Link href="/settings/modules" className="btn-primary w-full px-4 py-2.5">
                {t("upsell.add")}
              </Link>
            ) : (
              <p role="note" className="w-full rounded-xl bg-surface p-3 text-sm">
                {t("upsell.askOwner", { module: upsell?.name ?? "" })}
              </p>
            )}
          </>
        ) : (
          <>
            <p className="text-muted">{t(`closed.${agent.state}` as "closed.disabled", { name: agent.name })}</p>
            {onEdit && (
              <button type="button" onClick={onEdit} className="btn-secondary px-4 py-2 text-sm">
                {t("edit.open")}
              </button>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
