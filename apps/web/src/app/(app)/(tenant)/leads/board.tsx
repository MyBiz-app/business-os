"use client";

import { ArrowRightLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useContext, useState, useTransition, type DragEvent, type ReactNode } from "react";

import { IconButton } from "@/components/ui/button";
import { Menu } from "@/components/ui/menu";
import { cx } from "@/components/ui/cx";

import { moveLeadStage } from "./actions";

type Stage = Parameters<typeof moveLeadStage>[1];

const Move = createContext<(leadId: string, stage: Stage) => void>(() => {});

/** Wraps the board: moving a card calls the server, then the page shows the new order. A failed
 * move says so instead of leaving the card where the person did not put it. */
export function BoardProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("leads");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const move = (leadId: string, stage: Stage) =>
    start(async () => {
      const result = await moveLeadStage(leadId, stage);
      setError(result.error ?? null);
    });
  return (
    <Move.Provider value={move}>
      <div aria-busy={pending}>
        {error && (
          <p role="alert" className="mb-2 text-sm text-danger">
            {t("moveFailed")}
          </p>
        )}
        {children}
      </div>
    </Move.Provider>
  );
}

/** A column that accepts a dragged card. Keyboard and touch use the card's "Move to" menu instead. */
export function StageDrop({ stage, canMove, className, children, "aria-labelledby": labelledBy }: { stage: Stage; canMove: boolean; className?: string; children: ReactNode; "aria-labelledby": string }) {
  const move = useContext(Move);
  const [over, setOver] = useState(false);
  if (!canMove) return <section aria-labelledby={labelledBy} className={className}>{children}</section>;
  const accepts = (event: DragEvent) => event.dataTransfer.types.includes("application/x-lead");
  return (
    <section
      aria-labelledby={labelledBy}
      className={cx(className, over && "ring-2 ring-primary")}
      onDragOver={(event) => {
        if (!accepts(event)) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        setOver(false);
        const id = event.dataTransfer.getData("application/x-lead");
        if (id) {
          event.preventDefault();
          move(id, stage);
        }
      }}
    >
      {children}
    </section>
  );
}

/** A draggable card with a "Move to" menu (the keyboard and touch way to change a stage). */
export function DraggableCard({
  leadId,
  stage,
  stages,
  canMove,
  name,
  children,
}: {
  leadId: string;
  stage: Stage;
  stages: { value: Stage; label: string }[];
  canMove: boolean;
  name: string;
  children: ReactNode;
}) {
  const t = useTranslations("leads");
  const move = useContext(Move);
  if (!canMove) return <>{children}</>;
  return (
    <div
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData("application/x-lead", leadId);
        event.dataTransfer.effectAllowed = "move";
      }}
      className="group relative"
    >
      {children}
      <div className="absolute end-1.5 top-1.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100 max-sm:opacity-100">
        <Menu
          label={t("moveTo", { name })}
          items={stages.filter((s) => s.value !== stage).map((s) => ({ key: s.value, label: s.label, onSelect: () => move(leadId, s.value) }))}
          trigger={(props) => (
            <IconButton {...props} label={t("moveTo", { name })}>
              <ArrowRightLeft aria-hidden="true" className="size-4" />
            </IconButton>
          )}
        />
      </div>
    </div>
  );
}
